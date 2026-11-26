"""Synthetic adversarial checks for the allocation books and paired drawdown audit."""
from copy import deepcopy
from datetime import date, timedelta
from unittest import TestCase

from agenthon_financial.allocation_books import allocation_entries
from agenthon_financial.allocation_verify import verify_allocation, verify_interval
from agenthon_financial.analysis import group
from agenthon_financial.cost_books import _summaries
from agenthon_financial.study import books, fit_weights
from agenthon_financial.weekly_books import weekly_entries


class AllocationVerifierTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = dict(initial_cash=10000., evaluation_years=[2020, 2021],
                        scenarios={"base": [5, 50, 10]}, arms=["momentum20", "passive_mix"])
        cls.rows, observations = [], []
        first, last = date(2019, 12, 1), date(2021, 1, 10)
        monday_quotes = {"2020-01-06": 100., "2020-01-13": 150.,
                         "2020-01-20": 80., "2020-01-27": 80.}
        for i in range((last - first).days + 1):
            day = str(first + timedelta(days=i))
            close = 50. if day == "2020-02-02" else 100. + .03*i
            cls.rows.append(dict(date=day, open=close, close=close, price_5=monday_quotes.get(day, close),
                                 minute_5=8))
            momentum = close/cls.rows[i-20]["close"] - 1 if i >= 20 else None
            observations.append(dict(date=day, momentum20=momentum,
                                     targets={"momentum20": int(momentum is not None and momentum > 0)}))
        weights = fit_weights(observations, cls.spec["evaluation_years"])
        baseline = group(books(cls.rows, observations, weights, cls.spec))
        full = weekly_entries(cls.rows, observations, cls.spec, "base")
        target, control = allocation_entries(cls.rows, full, "base", cls.spec["scenarios"]["base"])
        cls.paths = {arm: path for (_, arm), path in baseline.items()}
        cls.paths.update(weekly20=full, target50=target, half_funded=control)
        cls.metrics = _summaries([e for path in cls.paths.values() for e in path], 10000.)

    def check(self, paths=None, rows=None, metrics=None):
        return verify_allocation(self.rows if rows is None else rows, self.spec, "base",
                                 self.paths if paths is None else paths,
                                 self.metrics if metrics is None else metrics)

    def test_positive_cost_first_fill_drift_and_unchanged_quote(self):
        receipt = self.check()
        self.assertEqual(receipt["status"], "passed")
        first = receipt["accounts"]["target50"]["first_fill"]
        self.assertEqual(first["date"], "2020-01-06")
        self.assertAlmostEqual(first["post_weight"], .5)
        self.assertAlmostEqual(receipt["accounts"]["half_funded"]["first_fill"]["post_weight"],
                               1/(1+1.005*1.001))
        self.assertGreater(receipt["first_fill_target_minus_control_pp"], 0)
        by_day = {r["date"]: r for r in self.paths["target50"]}
        self.assertLess(by_day["2020-01-13"]["trade_quantity"], 0)
        self.assertGreater(by_day["2020-01-20"]["trade_quantity"], 0)
        self.assertEqual(by_day["2020-01-27"]["trade_quantity"], 0)
        self.assertEqual(by_day["2020-02-03"]["shares"], 0)
        self.assertEqual(by_day["2020-12-31"]["shares"], by_day["2021-01-01"]["shares"])

    def test_corrupted_entries_rejected(self):
        for arm, day, field, value in (
            ("target50", "2020-01-01", "target_for_open", .5),
            ("target50", "2020-01-06", "execution_time", "2020-01-06T00:05:00Z"),
            ("target50", "2020-01-13", "fee", 0.), ("target50", "2020-01-20", "slippage_cost", 0.),
            ("target50", "2020-01-27", "trade_quantity", 1e-12),
            ("target50", "2020-01-07", "trade_quantity", 1e-12),
            ("target50", "2020-02-03", "shares", 1e-12),
            ("half_funded", "2020-01-06", "cash", 0.),
            ("half_funded", "2020-01-07", "daily_return", .5*self.paths["weekly20"][6]["daily_return"]),
            ("target50", "2021-01-01", "shares", 0.),
        ):
            with self.subTest(arm=arm, day=day, field=field):
                paths = dict(self.paths)
                paths[arm] = [dict(row, **{field: value}) if row["date"] == day else row
                              for row in paths[arm]]
                with self.assertRaisesRegex(ValueError, field):
                    self.check(paths=paths)

    def test_changed_source_and_metrics_do_not_verify(self):
        # This is the lagged close for the first Sunday's 20-session signal.
        rows = [dict(bar, close=900.) if bar["date"] == "2019-12-16" else bar for bar in self.rows]
        with self.assertRaises(ValueError):
            self.check(rows=rows)
        for arm, period, field in (("half_funded", "pooled", "sharpe"),
                                  ("target50", "2021", "starting_equity"),
                                  ("target50", "2020", "max_drawdown"),
                                  ("half_funded", "pooled", "max_drawdown")):
            with self.subTest(arm=arm, period=period, field=field):
                metrics = deepcopy(self.metrics)
                metrics[arm][period][field] += .1
                with self.assertRaisesRegex(ValueError, field):
                    self.check(metrics=metrics)


class AllocationIntervalTests(TestCase):
    def setUp(self):
        self.spec = dict(initial_cash=10000., evaluation_years=[2020, 2021],
                         uncertainty=dict(draws=5, block_sessions=2, seed=20261121))
        dates = [(date(2020, 12, 29) + timedelta(days=i)).isoformat() for i in range(6)]
        self.paths = {}
        for arm, returns in (("weekly20", [.5, -.4, .3, -.5, .5, .2]),
                             ("target50", [.25, -.15, .18, -.21, .12, .08])):
            wealth = 10000.
            self.paths[arm] = []
            for day, change in zip(dates, returns, strict=True):
                wealth *= 1 + change
                self.paths[arm].append(dict(date=day, daily_return=change, equity=wealth))
        # Five scalar paired draws, whole-path drawdown in points, in replicate
        # order: 0.639320, 14.855728, 16.629886, 14.718861, 13.421186.
        # The first draw selects indices 1,2,1 | 3,4,3. The $5,000 reserve
        # stays fixed as the active sleeve compounds through the second year.
        self.primary = dict(difference_pp=15.6, interval95_pp=[1.9175066440678168, 16.45247041845628])

    def test_wraparound_fold_truncation_and_continuous_reserve(self):
        result = verify_interval(self.paths, self.spec, self.primary)
        self.assertTrue(result["fixed_reserve_preserved"])
        self.assertEqual(result["draws"], 5)

    def test_incorrect_sign_interval_or_date_is_rejected(self):
        for field, value in (("difference_pp", -15.6), ("interval95_pp", [1.91, 16.45])):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                verify_interval(self.paths, self.spec, dict(self.primary, **{field: value}))
        self.paths["target50"][1]["date"] = "2020-12-31"
        with self.assertRaisesRegex(ValueError, "dates"):
            verify_interval(self.paths, self.spec, self.primary)
