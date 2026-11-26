"""Synthetic timing and information-boundary checks for the single weekly rule."""
import copy
from datetime import date, timedelta
from unittest import TestCase

from agenthon_financial.study import frozen, signals
from agenthon_financial.weekly_books import weekly_entries


class WeeklyBookTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = {**frozen()[0], "evaluation_years": [2020, 2021]}
        first, last = date(2019, 9, 1), date(2021, 1, 12)
        cls.rows = []
        for i in range((last - first).days + 1):
            day = first + timedelta(days=i)
            price = 100.0 + i + (i % 5) / 10
            # Midweek daily momentum turns down. The weekly account must hold
            # until the next Sunday close, then sell at Monday's delayed quote.
            if date(2020, 1, 7) <= day <= date(2020, 1, 12):
                price = 75.0
            cls.rows.append(dict(date=str(day), open=price - 1, close=price,
                                 price_5=price - .3, minute_5=7))
        cls.features, _ = signals(cls.rows, cls.spec)
        cls.base = weekly_entries(cls.rows, cls.features, cls.spec, "base")
        cls.days = {e["date"]: e for e in cls.base}

    def test_initial_cash_and_next_monday_fill(self):
        for day in self.base[:5]:
            self.assertEqual((day["cash"], day["shares"], day["fee"]), (10000, 0, 0))
            for key in ("signal_session", "feature_cutoff", "decision_time",
                        "execution_time", "target_for_open"):
                self.assertIsNone(day[key])
        purchase = self.days["2020-01-06"]
        self.assertEqual(purchase["signal_session"], "2020-01-05")
        self.assertEqual(purchase["feature_cutoff"], purchase["decision_time"])
        self.assertEqual(purchase["decision_time"], "2020-01-06T00:00:00Z")
        self.assertEqual(purchase["execution_time"], "2020-01-06T00:07:00Z")
        self.assertEqual(purchase["execution_proxy_time"], purchase["execution_time"])
        fill = purchase["quote"] * 1.001
        quantity = 10000 / (fill * 1.005)
        self.assertAlmostEqual(purchase["shares"], quantity)
        self.assertAlmostEqual(purchase["fee"], quantity * fill * .005)
        self.assertEqual(purchase["target_for_open"], 1)

    def test_hold_until_next_monday_and_carry_across_new_year(self):
        purchase = self.days["2020-01-06"]
        for day in self.base[6:12]:
            self.assertEqual(day["shares"], purchase["shares"])
            self.assertIsNone(day["decision_time"])
            self.assertEqual(day["trade_quantity"], 0)
        sale = self.days["2020-01-13"]
        self.assertEqual(sale["signal_session"], "2020-01-12")
        self.assertEqual(sale["target_for_open"], 0)
        self.assertEqual(sale["trade_quantity"], -purchase["shares"])
        self.assertAlmostEqual(sale["cash"], purchase["shares"] * sale["quote"] * .999 * .995)
        jan1 = self.days["2021-01-01"]
        self.assertIsNone(jan1["target_for_open"])
        self.assertGreater(jan1["shares"], 0)
        self.assertEqual(jan1["shares"], self.days["2020-12-31"]["shares"])
        self.assertEqual(self.days["2021-01-04"]["signal_session"], "2021-01-03")
        self.assertIsNone(self.days["2021-01-04"]["execution_time"])

    def test_unchanged_results_before_future_price_changes(self):
        revised = copy.deepcopy(self.rows)
        for bar in revised:
            if bar["date"] >= "2020-01-11":
                for key in ("open", "close", "price_5"):
                    bar[key] *= 3
        obs, _ = signals(revised, self.spec)
        rerun = weekly_entries(revised, obs, self.spec, "base")
        self.assertEqual(rerun[:10], self.base[:10])
        self.assertEqual(rerun[12]["target_for_open"], 1)
        self.assertEqual(self.base[12]["target_for_open"], 0)

    def test_equality_is_cash_and_missing_sunday_signal_is_rejected(self):
        idx = next(i for i, f in enumerate(self.features) if f["date"] == "2020-01-05")
        features = list(self.features)
        features[idx] = dict(features[idx], momentum20=0.)
        self.assertEqual(weekly_entries(self.rows, features, self.spec, "gross")[5]["target_for_open"], 0)
        for bad in (None, float("nan")):
            features[idx] = dict(features[idx], momentum20=bad)
            with self.assertRaisesRegex(ValueError, "completed momentum"):
                weekly_entries(self.rows, features, self.spec, "gross")

    def test_sunday_cannot_be_skipped_or_relabelled(self):
        idx = next(i for i, r in enumerate(self.rows) if r["date"] == "2020-01-05")
        with self.assertRaisesRegex(ValueError, "contiguous"):
            weekly_entries(self.rows[:idx]+self.rows[idx+1:], self.features[:idx]+self.features[idx+1:],
                           self.spec, "base")
        features = list(self.features)
        features[idx] = dict(features[idx], date="2020-01-06")
        with self.assertRaisesRegex(ValueError, "dates differ"):
            weekly_entries(self.rows, features, self.spec, "base")
