"""Deliberate mutations of the weekly cadence ledger on synthetic UTC sessions."""
from copy import deepcopy
from datetime import date, timedelta
from unittest import TestCase

from agenthon_financial.analysis import summarize
from agenthon_financial.weekly_books import weekly_entries
from agenthon_financial.weekly_verify import verify_weekly


class WeeklyVerifierTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = {"evaluation_years": [2020, 2021], "initial_cash": 1000.,
                    "scenarios": {"base": [5, 50, 10]}}
        cls.rows, features = [], []
        day = date(2019, 12, 1)
        while day <= date(2021, 1, 8):
            i = len(cls.rows)
            close = 100. + i / 10
            if day == date(2020, 1, 12):
                close = cls.rows[i-20]["close"]  # Exact equality instructs the second Monday sale.
            cls.rows.append(dict(date=str(day), close=close, open=close, price_5=close + .5, minute_5=7))
            momentum = close / cls.rows[i-20]["close"] - 1 if i >= 20 else None
            features.append(dict(date=str(day), momentum20=momentum))
            day += timedelta(days=1)
        cls.book = weekly_entries(cls.rows, features, cls.spec, "base")
        cls.summary = {"pooled": summarize(cls.book, 1000.)}
        start = 1000.
        for year in ["2020", "2021"]:
            part = [e for e in cls.book if e["date"].startswith(year)]
            cls.summary[year] = summarize(part, start)
            start = part[-1]["equity"]

    def check(self, book=None, summaries=None, rows=None):
        return verify_weekly(self.rows if rows is None else rows, self.spec, "base",
                             self.book if book is None else book,
                             self.summary if summaries is None else summaries)

    def test_synthetic_wait_tie_and_continuous_hold(self):
        receipt = self.check()
        self.assertEqual(receipt["first_scheduled_session"], "2020-01-06")
        self.assertEqual(receipt["fills"], 3)
        self.assertEqual(receipt["period_summaries"], 3)
        dated = {r["date"]: r for r in self.book}
        self.assertEqual(dated["2020-01-05"]["shares"], 0)
        self.assertEqual(dated["2020-01-13"]["target_for_open"], 0)
        self.assertGreater(dated["2020-01-13"]["fee"], 0)
        self.assertEqual(dated["2020-12-31"]["shares"], dated["2021-01-01"]["shares"])
        self.assertGreater(dated["2021-01-01"]["shares"], 0)

    def test_schedule_cost_and_balance_mutations(self):
        mutations = [
            ("2020-01-01", "decision_time", "2020-01-01T00:00:00Z"),
            ("2020-01-06", "signal_session", "2020-01-06"),
            ("2020-01-06", "execution_time", "2020-01-06T00:05:00Z"),  # Actual quote at 00:07.
            ("2020-01-06", "feature_cutoff", "2020-01-06T00:07:00Z"),
            ("2020-01-06", "fill_price", 100.0),
            ("2020-01-06", "fee", 0.0),
            ("2020-01-06", "slippage_cost", 0.0),
            ("2020-01-07", "trade_quantity", 1e-12),  # Even a small unscheduled fill must fail.
            ("2020-01-13", "target_for_open", 1),
            ("2020-01-13", "cash", 1000.0),
            ("2021-01-01", "shares", 0.0),
        ]
        by_day = {e["date"]: i for i, e in enumerate(self.book)}
        for day, field, value in mutations:
            altered = self.book.copy()
            index = by_day[day]
            altered[index] = {**self.book[index], field: value}
            with self.subTest(day=day, field=field), self.assertRaisesRegex(ValueError, field):
                self.check(book=altered)

    def test_replay_rejects_source_close_behind_wrong_decision(self):
        # Reprice only the development-period reference for the first decision.
        changed = [dict(r, close=1e4) if r["date"] == "2019-12-16" else r for r in self.rows]
        with self.assertRaisesRegex(ValueError, "2020-01-06"):
            self.check(rows=changed)

    def test_summary_requires_carried_opening_and_correct_pooled_risk(self):
        for period, field in [("2021", "starting_equity"), ("pooled", "sharpe"),
                              ("2020", "turnover"), ("pooled", "transaction_cost")]:
            broken = deepcopy(self.summary)
            broken[period][field] += 1
            with self.subTest(period=period, field=field), self.assertRaisesRegex(ValueError, field):
                self.check(summaries=broken)

    def test_incomplete_records_do_not_pass(self):
        with self.assertRaises(ValueError):
            self.check(book=self.book[:-1])
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            self.check(rows=self.rows[:25] + self.rows[26:])
