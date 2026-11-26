"""Check the public sensitivity exhibit against the released daily evidence."""
import calendar
import gzip
import hashlib
import json
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/btc-financial-v1"
EXPERIMENT = ROOT / "experiments/btc-financial-v1"
METRICS = ("ending_equity", "total_return", "sharpe", "max_drawdown",
           "mean_close_exposure", "trade_events", "transaction_cost")


class PublicScenarioTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = json.loads((ROOT / "site-export/btc-study.json").read_bytes())
        cls.spec = json.loads((EXPERIMENT / "protocol.json").read_bytes())

    def test_month_end_marks_match_actual_close_for_each_arm_and_cost(self):
        expected = {}
        with gzip.open(REPORT / "ledger.jsonl.gz", "rt", encoding="ascii") as stream:
            for line in stream:
                row = json.loads(line)
                year, month, day = map(int, row["date"].split("-"))
                if day == calendar.monthrange(year, month)[1] and row["scenario"] != "later_fill":
                    expected[row["scenario"], row["arm"], row["date"]] = (row["equity"], row["drawdown"])
        for scenario, exhibit in self.public["scenarios"].items():
            marks = exhibit["month_ends"]
            self.assertEqual(len(marks), 60)
            self.assertEqual([m["date"] for m in marks], sorted(m["date"] for m in marks))
            for mark in marks:
                self.assertEqual(mark.keys(), {"date", *self.spec["arms"]})
                for arm in self.spec["arms"]:
                    equity, drawdown = expected.pop((scenario, arm, mark["date"]))
                    self.assertEqual(mark[arm], {"equity": equity, "drawdown": drawdown})
        self.assertEqual(expected, {})

    def test_assumptions_pooled_metrics_and_inference_scope(self):
        metrics = json.loads((REPORT / "metrics.json").read_bytes())
        self.assertEqual(self.public["schema_version"], 2)
        self.assertEqual(set(self.public["scenarios"]), {"gross", "base", "double_cost"})
        self.assertEqual(self.public["interval95"], metrics["interval95"])
        self.assertIn("base Sharpe difference", self.public["inference_scope"])
        self.assertNotIn("month_ends", self.public["later_fill"])
        for name, exhibit in {**self.public["scenarios"], "later_fill": self.public["later_fill"]}.items():
            self.assertEqual([exhibit[k] for k in self.spec["scenario_units"]], self.spec["scenarios"][name])
            self.assertEqual(exhibit["sharpe_delta"], metrics["sharpe_delta"][name]["pooled"])
            self.assertEqual(exhibit["portfolios"].keys(), set(self.spec["arms"]))
            for arm in self.spec["arms"]:
                pooled = metrics["portfolios"][name][arm]["pooled"]
                self.assertEqual(exhibit["portfolios"][arm], {k: pooled[k] for k in METRICS})
                self.assertAlmostEqual(pooled["transaction_cost"], pooled["fees"] + pooled["slippage_cost"])

    def test_provenance_binds_the_exact_published_evidence(self):
        for field, path in (
            ("original_receipt_sha256", REPORT / "run.json"), ("ledger_sha256", REPORT / "ledger.jsonl.gz"),
            ("verification_sha256", REPORT / "verification.json"), ("metrics_sha256", REPORT / "metrics.json"),
            ("source_manifest_sha256", EXPERIMENT / "source.json"), ("inputs_sha256", EXPERIMENT / "sessions.csv"),
            ("protocol_sha256", EXPERIMENT / "protocol.json"),
        ):
            self.assertEqual(self.public[field], hashlib.sha256(path.read_bytes()).hexdigest())
        source = json.loads((EXPERIMENT / "source.json").read_bytes())
        self.assertEqual(self.public["license_url"], source["license_url"])
        self.assertEqual(self.public["evidence"]["publisher_terms_url"], source["publisher_terms"])
        self.assertEqual(self.public["verification"], "passed")
