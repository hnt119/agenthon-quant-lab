"""Authored regression cases: these are unrelated to competition test data."""

import copy
import csv
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import tempfile
import unittest

from agenthon_quant.trading import load_prices, run, signals, verify_ledger


def make_rows(prices):
    return [{"date": (date(2025, 1, 1) + timedelta(days=i)).isoformat(), "open": p[0], "close": p[1]}
            for i, p in enumerate(prices)]


def spec_for(rows, **updates):
    spec = {"workflow": "trading", "data": "prices.csv", "source": "authored test fixture",
            "price_adjustment": "unadjusted", "timestamp_convention": "session_date",
            "initial_cash": 120.0, "fee_bps": 0.0, "slippage_bps": 0.0,
            "lookback": 2, "development_end": rows[2]["date"], "holdout_start": rows[3]["date"],
            "synthetic": True}
    spec.update(updates)
    return spec


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "close"])
        writer.writeheader()
        writer.writerows(rows)


class TradingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "prices.csv"
        self.rows = make_rows([(10, 10), (10, 12), (12, 15), (15, 9), (9, 8), (8, 10)])
        write_csv(self.path, self.rows)

    def evaluate(self, **updates):
        return run(spec_for(self.rows, **updates), self.path)

    def test_tiny_hand_reconciliation_and_benchmark(self):
        result = self.evaluate()
        gross = result["results"]["strategy"]["gross"]
        self.assertEqual([x["equity"] for x in gross["ledger"]], [120, 120, 150, 90, 90, 90])
        self.assertEqual([x["shares"] for x in gross["ledger"]], [0, 0, 10, 10, 0, 0])
        self.assertEqual([x["cash"] for x in gross["ledger"]], [120, 120, 0, 0, 90, 90])
        self.assertEqual([x["pnl"] for x in gross["ledger"]], [0, 0, 30, -60, 0, 0])
        self.assertEqual([x["signal_date"] for x in gross["trades"]], ["2025-01-02", "2025-01-04"])
        self.assertEqual([x["date"] for x in gross["trades"]], ["2025-01-03", "2025-01-05"])
        self.assertAlmostEqual(gross["metrics"]["total_return"], -0.25)
        self.assertAlmostEqual(gross["metrics"]["max_drawdown"], 0.4)
        self.assertAlmostEqual(gross["metrics"]["turnover"], 2.0)
        self.assertAlmostEqual(gross["metrics"]["mean_close_exposure"], 2 / 6)
        self.assertAlmostEqual(gross["periods"]["development"]["total_return"], 0.25)
        self.assertAlmostEqual(gross["periods"]["holdout"]["total_return"], -0.4)
        benchmark = result["results"]["buy_and_hold"]["gross"]
        self.assertEqual(benchmark["metrics"]["ending_equity"], 100)
        self.assertEqual(len(benchmark["trades"]), 1)
        self.assertEqual(benchmark["metrics"]["ending_shares"], 10)
        self.assertTrue(all(x["status"] == "passed" for x in result["checks"][:-1]))
        self.assertEqual(result["checks"][-1]["status"], "unavailable")

    def test_costs_are_affordable_and_reconcile_independently(self):
        net = self.evaluate(fee_bps=100, slippage_bps=100)["results"]["strategy"]["net"]
        # Entry: 120 / (12 * 1.01 * 1.01), exit: q * 9 * .99 * .99.
        quantity = 120 / 12.2412
        ending_cash = quantity * 8.8209
        self.assertAlmostEqual(net["trades"][0]["quantity"], quantity)
        self.assertAlmostEqual(net["metrics"]["ending_equity"], ending_cash)
        expected_fees = quantity * (12.12 + 8.91) * .01
        expected_slippage = quantity * (.12 + .09)
        self.assertAlmostEqual(net["metrics"]["fees"], expected_fees)
        self.assertAlmostEqual(net["metrics"]["slippage_cost"], expected_slippage)
        self.assertAlmostEqual(net["metrics"]["transaction_cost"], expected_fees + expected_slippage)
        for entry in net["ledger"]:
            self.assertGreaterEqual(entry["cash"], -1e-10)
            self.assertAlmostEqual(entry["pnl"], entry["overnight_pnl"] + entry["intraday_pnl"] - entry["fee"] - entry["slippage_cost"])

    def test_future_observations_cannot_change_earlier_decisions(self):
        original = self.evaluate()
        changed = copy.deepcopy(self.rows)
        changed[-2]["open"], changed[-2]["close"] = 900, 1000
        changed[-1]["open"], changed[-1]["close"] = 1100, 1200
        write_csv(self.path, changed)
        future = self.evaluate()
        for name in ("strategy", "buy_and_hold"):
            for costs in ("gross", "net"):
                self.assertEqual(original["results"][name][costs]["ledger"][:4], future["results"][name][costs]["ledger"][:4])

    def test_current_close_does_not_affect_current_open_execution(self):
        original = self.evaluate()["results"]["strategy"]["gross"]["ledger"]
        changed = copy.deepcopy(self.rows)
        changed[2]["close"] = 1
        write_csv(self.path, changed)
        future = self.evaluate()["results"]["strategy"]["gross"]["ledger"]
        self.assertEqual(original[2]["trade_quantity"], future[2]["trade_quantity"])
        self.assertNotEqual(original[2]["target_at_close"], future[2]["target_at_close"])

    def test_final_close_signal_is_not_executed(self):
        result = self.evaluate()["results"]["strategy"]["gross"]
        self.assertEqual(result["ledger"][-1]["target_at_close"], 1)
        self.assertEqual(result["ledger"][-1]["shares"], 0)
        self.assertEqual(len(result["trades"]), 2)

    def test_no_same_day_information_or_duplicate_entries(self):
        ledger = self.evaluate()["results"]["strategy"]["gross"]["ledger"]
        self.assertEqual(ledger[1]["trade_quantity"], 0)
        self.assertGreater(ledger[2]["trade_quantity"], 0)
        self.assertEqual(ledger[3]["trade_quantity"], 0)
        self.assertLess(ledger[4]["trade_quantity"], 0)

    def test_corrupted_cash_is_detected(self):
        ledger = self.evaluate()["results"]["strategy"]["gross"]["ledger"]
        ledger[2]["cash"] += 3
        checks = verify_ledger(ledger, self.rows, 120, lookback=2)
        self.assertIn("cash_shares_equity_reconciliation", [x["name"] for x in checks if x["status"] == "failed"])

    def test_corrupted_timing_and_pnl_are_detected(self):
        ledger = self.evaluate()["results"]["strategy"]["gross"]["ledger"]
        ledger[2]["signal_date"] = ledger[2]["date"]
        ledger[2]["pnl"] += 1
        checks = verify_ledger(ledger, self.rows, 120, lookback=2)
        self.assertIn("signal_and_execution_timing", [x["name"] for x in checks if x["status"] == "failed"])
        self.assertIn("pnl_reconciliation", [x["name"] for x in checks if x["status"] == "failed"])

    def test_corrupted_fee_and_duplicate_trade_are_detected(self):
        ledger = self.evaluate(fee_bps=10)["results"]["strategy"]["net"]["ledger"]
        ledger[2]["fee"] = 0
        ledger[3]["trade_quantity"] = ledger[2]["trade_quantity"]
        checks = verify_ledger(ledger, self.rows, 120, fee_bps=10, lookback=2)
        failures = [x["name"] for x in checks if x["status"] == "failed"]
        self.assertIn("fee_slippage_reconciliation", failures)
        self.assertIn("signal_and_execution_timing", failures)

    def test_equal_mean_is_flat(self):
        flat = make_rows([(10, 10)] * 6)
        self.assertEqual(signals(flat, 2), [0] * 6)

    def test_period_returns_compound_to_full_return(self):
        result = self.evaluate(fee_bps=23, slippage_bps=17)
        for name in ("strategy", "buy_and_hold"):
            for kind in ("gross", "net"):
                portfolio = result["results"][name][kind]
                before = portfolio["periods"]["development"]["total_return"]
                after = portfolio["periods"]["holdout"]["total_return"]
                self.assertAlmostEqual((1 + before) * (1 + after) - 1, portfolio["metrics"]["total_return"])

    def test_invalid_spec_rejected(self):
        cases = [{"lookback": True}, {"lookback": 1}, {"lookback": 2.5}, {"fee_bps": -1},
                 {"slippage_bps": 10000}, {"fee_bps": float("nan")}, {"initial_cash": 0},
                 {"price_adjustment": "dividend_adjusted"}, {"timestamp_convention": "UTC"},
                 {"source": ""}, {"surprise": 1}, {"synthetic": "yes"},
                 {"holdout_start": "2025-01-05"}, {"development_end": "2024-01-01"}]
        for update in cases:
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.evaluate(**update)

    def test_duplicate_or_unsorted_dates_rejected(self):
        for change in (lambda x: x.append(x[-1]), lambda x: x.reverse()):
            changed = copy.deepcopy(self.rows)
            change(changed)
            write_csv(self.path, changed)
            with self.assertRaisesRegex(ValueError, "strictly increasing"):
                load_prices(self.path)

    def test_nonfinite_negative_or_missing_prices_rejected(self):
        for value in (0, -1, float("nan"), float("inf"), ""):
            changed = copy.deepcopy(self.rows)
            changed[2]["close"] = value
            write_csv(self.path, changed)
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_prices(self.path)
        self.path.write_text("date,close\n2025-01-01,10\n")
        with self.assertRaisesRegex(ValueError, "date, open, and close"):
            load_prices(self.path)

    def test_csv_header_and_row_shape_rejected(self):
        for text in ("date,open,close,close\n2025-01-01,1,1,1\n", "date,open,close\n2025-01-01,1,1,extra\n"):
            self.path.write_text(text)
            with self.assertRaises(ValueError):
                load_prices(self.path)

    def test_finite_but_unrepresentable_portfolio_is_rejected(self):
        changed = copy.deepcopy(self.rows)
        for row in changed:
            row["open"] *= 1e-300
            row["close"] *= 1e-300
        write_csv(self.path, changed)
        with self.assertRaisesRegex(ValueError, "numeric range"):
            self.evaluate(initial_cash=1e300)

    @unittest.skipUnless(importlib.util.find_spec("pyarrow"), "optional PyArrow not installed")
    def test_parquet_csv_equivalence(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        target = self.path.with_suffix(".parquet")
        pq.write_table(pa.Table.from_pylist(self.rows), target)
        csv_result = self.evaluate()
        parquet_result = run(spec_for(self.rows), target)
        self.assertEqual(csv_result, parquet_result)

    def test_example_and_generator_are_consistent(self):
        module_path = Path(__file__).resolve().parents[1] / "scripts" / "generate_synthetic_data.py"
        module_spec = importlib.util.spec_from_file_location("generate_synthetic_data", module_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        target = self.path.with_name("generated.csv")
        module.generate(target)
        expected = module_path.parents[1] / "examples" / "data" / "synthetic_prices.csv"
        self.assertEqual(target.read_bytes(), expected.read_bytes())


if __name__ == "__main__":
    unittest.main()
