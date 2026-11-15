"""Historical portfolio accounting on independently calculated session prices."""

import copy
import json
import unittest

from agenthon_quant import historical, trading


def fixture():
    # Buy 10 shares at 12 on day 3 (train). Sell at 8 on day 5
    # (validation). Buy 8 shares at 10 on day 7 (test).
    prices = [(10, 10), (10, 12), (12, 15), (15, 9), (8, 8), (8, 10), (10, 11), (11, 7)]
    rows = [{"date": f"2025-01-{i:02d}", "open": opening, "close": closing}
            for i, (opening, closing) in enumerate(prices, 1)]
    spec = {"workflow": "historical", "data": "authored.csv", "source": "Hand calculation",
            "synthetic": True, "price_adjustment": "unadjusted", "timestamp_convention": "session_date",
            "initial_cash": 120, "lookback": 2, "train_end": "2025-01-03", "validation_end": "2025-01-05"}
    return spec, rows


class HistoricalTests(unittest.TestCase):
    def setUp(self):
        self.spec, self.rows = fixture()

    def calculate(self, **changes):
        return historical.evaluate({**self.spec, **changes}, self.rows, {"observation_count": len(self.rows)})

    def test_strategy_net_gross_and_continuous_splits(self):
        outcome = self.calculate()
        book = outcome["results"]["strategies"]["sma"]["gross"]
        self.assertEqual(outcome["results"]["dates"], [r["date"] for r in self.rows])
        self.assertEqual(book["equity"], [120, 120, 150, 90, 80, 80, 88, 56])
        self.assertAlmostEqual(book["metrics"]["total_return"], 56 / 120 - 1)
        self.assertAlmostEqual(book["metrics"]["turnover"], 3)
        self.assertEqual(book["metrics"]["trade_events"], 3)
        self.assertAlmostEqual(book["metrics"]["mean_close_exposure"], 4 / 8)
        self.assertAlmostEqual(book["metrics"]["ending_shares"], 8)
        self.assertEqual(book["metrics"]["ending_cash"], 0)
        for period, first, last, start, end in (("train", 0, 2, 120, 150), ("validation", 3, 4, 150, 80),
                                                ("test", 5, 7, 80, 56)):
            with self.subTest(period=period):
                stats = book["periods"][period]
                self.assertEqual(stats["start"], self.rows[first]["date"])
                self.assertEqual(stats["end"], self.rows[last]["date"])
                self.assertEqual(stats["observations"], last - first + 1)
                self.assertEqual(stats["starting_equity"], start)
                self.assertEqual(stats["ending_equity"], end)
                self.assertAlmostEqual(stats["total_return"], end / start - 1)
        self.assertEqual(book, outcome["results"]["strategies"]["sma"]["net"])
        self.assertFalse([c for c in outcome["checks"] if c["status"] == "failed"])
        self.assertTrue(any(c["status"] == "unavailable" for c in outcome["checks"]))

    def test_drawdown_full_peak_carries_but_period_peak_resets(self):
        book = self.calculate()["results"]["strategies"]["sma"]["gross"]
        full = [0, 0, 0, .4, 1 - 80/150, 1 - 80/150, 1 - 88/150, 1 - 56/150]
        for observed, expected in zip(book["drawdown"], full):
            self.assertAlmostEqual(observed, expected)
        self.assertAlmostEqual(book["metrics"]["max_drawdown"], max(full))
        self.assertAlmostEqual(book["periods"]["test"]["max_drawdown"], 1 - 56/88)
        self.assertAlmostEqual(book["periods"]["validation"]["max_drawdown"], 1 - 80/150)

    def test_cash_and_buy_and_hold_reference_paths_after_costs(self):
        books = self.calculate(fee_bps=100, slippage_bps=100)["results"]["strategies"]
        for cost in ("gross", "net"):
            with self.subTest(cost=cost):
                cash = books["cash"][cost]
                self.assertEqual(cash["equity"], [120] * 8)
                self.assertEqual(cash["drawdown"], [0] * 8)
                for key in ("total_return", "trade_events", "transaction_cost", "turnover", "mean_close_exposure"):
                    self.assertEqual(cash["metrics"][key], 0)
        buyhold = books["buy_and_hold"]
        self.assertEqual(buyhold["gross"]["equity"], [120, 120, 150, 90, 80, 100, 110, 70])
        quantity = 120 / (12.12 * 1.01)
        self.assertAlmostEqual(buyhold["net"]["metrics"]["ending_shares"], quantity)
        self.assertAlmostEqual(buyhold["net"]["metrics"]["ending_equity"], 7 * quantity)
        self.assertAlmostEqual(buyhold["net"]["metrics"]["fees"], quantity * 12.12 * .01)
        self.assertAlmostEqual(buyhold["net"]["metrics"]["slippage_cost"], quantity * .12)
        self.assertEqual(buyhold["net"]["metrics"]["trade_events"], 1)
        self.assertEqual(buyhold["net"]["periods"]["test"]["trade_events"], 0)

    def test_compounding_costs_and_marking_at_final_close(self):
        book = self.calculate(fee_bps=100, slippage_bps=100)["results"]["strategies"]["sma"]["net"]
        first_qty = 120 / (12.12 * 1.01)
        second_qty = (first_qty * 7.92 * .99) / (10.10 * 1.01)
        self.assertAlmostEqual(book["metrics"]["ending_equity"], second_qty * 7)
        self.assertAlmostEqual(book["metrics"]["ending_shares"], second_qty)
        self.assertAlmostEqual(book["metrics"]["fees"], (first_qty*(12.12+7.92) + second_qty*10.10)*.01)
        self.assertAlmostEqual(book["metrics"]["slippage_cost"], first_qty*(.12+.08)+second_qty*.10)
        self.assertAlmostEqual(book["metrics"]["transaction_cost"], book["metrics"]["fees"] + book["metrics"]["slippage_cost"])

    def test_changed_test_prices_do_not_affect_train_and_validation(self):
        before = self.calculate(fee_bps=5, slippage_bps=5)["results"]
        self.rows[-2]["open"] = 2000
        self.rows[-2]["close"] = 3000
        self.rows[-1]["open"] = 20
        after = self.calculate(fee_bps=5, slippage_bps=5)["results"]
        for name in historical.STRATEGIES:
            for cost in ("gross", "net"):
                a, b = before["strategies"][name][cost], after["strategies"][name][cost]
                self.assertEqual(a["equity"][:5], b["equity"][:5])
                self.assertEqual(a["drawdown"][:5], b["drawdown"][:5])
                for period in ("train", "validation"):
                    self.assertEqual(a["periods"][period], b["periods"][period])

    def test_invalid_boundaries_and_strategy_selection(self):
        for changes in ({"train_end": "2025-01-02"}, {"train_end": "2025-01-05"},
                        {"validation_end": "2025-01-08"}, {"train_end": "2025-01-30"},
                        {"strategies": []}, {"strategies": ["cash", "cash"]}, {"strategies": "sma"},
                        {"strategies": ["optimized"]}, {"unrecognized": True}, {"fee_bps": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.calculate(**changes)
        outcome = self.calculate(strategies=["cash", "sma"])
        self.assertEqual(list(outcome["results"]["strategies"]), ["cash", "sma", "buy_and_hold"])
        self.assertEqual(outcome["assumptions"]["requested_strategies"], ["cash", "sma"])
        self.assertEqual(list(self.calculate(strategies=["cash"])["results"]["strategies"]), ["cash", "buy_and_hold"])

    def test_material_cash_and_benchmark_corruption_detected(self):
        wrong_ledger = trading.simulate_ledger(self.rows, [1] * len(self.rows), 120, 0, 0)
        checks = trading.verify_ledger(wrong_ledger, self.rows, 120, strategy="cash", lookback=2)
        self.assertIn("signal_and_execution_timing", [c["name"] for c in checks if c["status"] == "failed"])
        outcome = self.calculate()
        eq = copy.deepcopy(outcome["results"]["strategies"]["buy_and_hold"]["net"]["equity"])
        eq[-1] += 1
        check = historical._benchmark_check("buy_and_hold", eq, self.rows, 120, 2, 0, 0)
        self.assertEqual((check["status"], check["failure_count"]), ("failed", 1))

    def test_summary_reconciliation_detects_shifted_boundary(self):
        ledger = trading.simulate_ledger(self.rows, trading.signals(self.rows, 2), 120, 0, 0)
        intervals = {"train": (0, 3), "validation": (3, 5), "test": (5, 8)}
        book = historical._summarize(ledger, 120, intervals)
        book["periods"]["test"]["starting_equity"] = 120
        check = historical._period_check(book, ledger, 120, intervals)
        self.assertEqual(check["status"], "failed")
        self.assertIn("test", check["details"])

    def test_compact_paths_have_no_detailed_quote_ledgers(self):
        result = self.calculate()["results"]
        for portfolio in result["strategies"].values():
            for book in portfolio.values():
                self.assertEqual(set(book), {"equity", "drawdown", "metrics", "periods"})
                self.assertEqual(len(result["dates"]), len(book["equity"]))
                self.assertEqual(len(result["dates"]), len(book["drawdown"]))
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
