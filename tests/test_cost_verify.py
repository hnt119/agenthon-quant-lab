from copy import deepcopy
from datetime import date, timedelta
from unittest import TestCase

from agenthon_financial.analysis import summarize
from agenthon_financial.cost_verify import _position, verify_cost_books
from agenthon_financial.study import books


class IndependentCostVerificationTests(TestCase):
    def test_post_cost_position_recovers_chosen_buy_and_sell(self):
        # Build targets from hand-specified trades with 1% fees and 0.2% slip.
        # Both start with $4,000 cash and 60 BTC quoted at $100.
        for chosen, price in [(7, 100.20), (-31, 99.80)]:
            held = 60 + chosen
            cash = 4000 - chosen * price - abs(chosen) * price * 0.01
            target = held * 100 / (cash + held * 100)
            balances = _position(4000, 60, target, 100, 0.01, 0.002)
            for actual, expected in zip(balances, (cash, held, chosen, price), strict=True):
                self.assertAlmostEqual(actual, expected)

    @classmethod
    def setUpClass(cls):
        cls.spec = {"evaluation_years": [2020, 2021], "initial_cash": 10_000.,
                    "scenarios": {"cost_path": [5, 25, 5]},
                    "arms": ["cash", "buy_and_hold", "momentum20", "momentum20_fft", "passive_mix"]}
        first = date(2019, 12, 31)
        cls.rows = []
        cls.obs = []
        for i in range(370):
            day = str(first + timedelta(days=i))
            close = 100 + i / 10 + i % 7
            cls.rows.append(dict(date=day, open=close, price_5=close + .5, minute_5=7, close=close))
            cls.obs.append(dict(targets=dict(cash=0, buy_and_hold=1, momentum20=int(i % 9 > 3),
                                             momentum20_fft=int(i % 9 > 3 and i % 2 == 0))))
        cls.weights = {2020: {"weight": .6}, 2021: {"weight": .25}}
        cls.entries = list(books(cls.rows, cls.obs, cls.weights, cls.spec))
        cls.portfolios = {}
        for arm in cls.spec["arms"]:
            path = [e for e in cls.entries if e["arm"] == arm]
            start = cls.spec["initial_cash"]
            metrics = {"pooled": summarize(path, start)}
            for year in ("2020", "2021"):
                section = [e for e in path if e["date"].startswith(year)]
                metrics[year] = summarize(section, start)
                start = section[-1]["equity"]
            cls.portfolios[arm] = metrics

    def verify(self, entries=None, portfolios=None):
        return verify_cost_books(self.rows, self.obs, self.weights, self.spec,
                                 self.entries if entries is None else entries,
                                 self.portfolios if portfolios is None else portfolios, 0.5)

    def test_all_books_carry_across_year_with_independent_terminal_values(self):
        checks = self.verify()
        self.assertEqual(checks["portfolio_sessions"], 369 * 5)
        self.assertEqual(checks["period_summaries"], 15)
        self.assertGreater(checks["fills"], 5)
        self.assertIsNone(self.portfolios["cash"]["pooled"]["sharpe"])

    def test_timing_cost_and_post_cost_balances_are_checked(self):
        # Corrupt the annual passive sale, where both holdings and cash survive.
        ix = next(i for i, e in enumerate(self.entries)
                  if e["date"] == "2021-01-01" and e["arm"] == "passive_mix")
        row = self.entries[ix]
        self.assertLess(row["trade_quantity"], 0)
        for key, value in (("execution_time", row["feature_cutoff"]), ("signal_session", row["date"]),
                           ("target_for_open", 0.5), ("fill_price", row["quote"]),
                           ("fee", float("nan")), ("slippage_cost", 0.),
                           ("cash", 10_000.), ("equity", None), ("shares", 0.)):
            copy = self.entries.copy()
            copy[ix] = dict(row, **{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                self.verify(entries=copy)

    def test_nulls_and_annual_carry_or_cost_misstatements_fail(self):
        for arm, period, key, value in (
                ("cash", "pooled", "sharpe", False),
                ("passive_mix", "2021", "starting_equity", 10_000.),
                ("momentum20", "2020", "transaction_cost", 0.),
                ("momentum20_fft", "pooled", "turnover", float("inf"))):
            summary = deepcopy(self.portfolios)
            summary[arm][period][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                self.verify(portfolios=summary)
