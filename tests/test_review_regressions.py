import copy
import csv
import tempfile
import unittest
from pathlib import Path

from agenthon_quant.records import execute, write_json
from agenthon_quant.trading import run, verify_ledger


class ReviewRegressions(unittest.TestCase):
    def test_finite_underflow_saves_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = {"workflow": "options", "spot": 1e-300, "strike": 1e-300,
                    "maturity_years": 1, "volatility": 1e-300, "rate": 0,
                    "dividend_yield": 0, "currency": "USD", "option_type": "both"}
            write_json(root / "spec.json", spec)
            record = execute(root / "spec.json", root / "run")
            self.assertEqual(record["status"], "invalid")
            self.assertTrue((root / "run/report.md").is_file())
            self.assertFalse((root / "run/validated-results.json").exists())

    def test_malformed_ledger_is_a_failed_check(self):
        rows = [{"date": "2026-01-01", "open": 100.0, "close": 100.0}]
        for malformed in (None, {}, [None], [[]], [12]):
            checks = verify_ledger(malformed, rows, 100.0)
            self.assertTrue(any(c["status"] == "failed" for c in checks), malformed)


class TradingNumericRegressions(unittest.TestCase):
    def evaluate(self, pairs, cash, fee_bps=23, slippage_bps=17):
        rows = [{"date": f"2025-01-{index + 1:02d}", "open": opening, "close": closing}
                for index, (opening, closing) in enumerate(pairs)]
        spec = {"workflow": "trading", "data": "prices.csv", "source": "authored numeric regression",
                "price_adjustment": "unadjusted", "timestamp_convention": "session_date",
                "initial_cash": cash, "lookback": 2, "fee_bps": fee_bps, "slippage_bps": slippage_bps,
                "development_end": "2025-01-03", "holdout_start": "2025-01-04", "synthetic": True}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["date", "open", "close"])
                writer.writeheader()
                writer.writerows(rows)
            return run(spec, path), rows

    def test_large_portfolios_reconcile_without_false_roundoff_failures(self):
        pairs = [(10, 10), (10, 12), (12, 15), (15, 9), (9, 8), (8, 10)]
        base, _ = self.evaluate(pairs, 120)
        for cash in (1e9, 1e10, 1e12, 1e14):
            with self.subTest(initial_cash=cash):
                report, _ = self.evaluate(pairs, cash)
                self.assertFalse([check for check in report["checks"] if check["status"] == "failed"])
                for strategy in ("strategy", "buy_and_hold"):
                    for treatment in ("gross", "net"):
                        portfolio = report["results"][strategy][treatment]
                        self.assertEqual(portfolio["ledger"][2]["cash"], 0.0)
                        self.assertAlmostEqual(portfolio["metrics"]["total_return"],
                                               base["results"][strategy][treatment]["metrics"]["total_return"], places=12)

    def test_meaningful_cash_and_pnl_corruption_still_detected_at_large_scale(self):
        pairs = [(10, 10), (10, 12), (12, 15), (15, 9), (9, 8), (8, 10)]
        report, rows = self.evaluate(pairs, 1e10)
        ledger = copy.deepcopy(report["results"]["strategy"]["net"]["ledger"])
        ledger[2]["cash"] += 1.0
        ledger[3]["pnl"] += 1.0
        checks = verify_ledger(ledger, rows, 1e10, fee_bps=23, slippage_bps=17, lookback=2)
        failures = {check["name"] for check in checks if check["status"] == "failed"}
        self.assertIn("cash_shares_equity_reconciliation", failures)
        self.assertIn("pnl_reconciliation", failures)
        self.assertEqual(ledger[2]["cash"], 1.0)  # verifier never repairs the supplied record

    def test_finite_inputs_with_overflowing_return_are_rejected(self):
        pairs = [(1e-300, 1e-300), (1e-300, 2e-300), (1e-300, 1e100),
                 (1e100, 1e100), (1e100, 1e100), (1e100, 1e100)]
        with self.assertRaisesRegex(ValueError, "summary metrics.*finite numeric range"):
            self.evaluate(pairs, 1e-300, fee_bps=0, slippage_bps=0)
