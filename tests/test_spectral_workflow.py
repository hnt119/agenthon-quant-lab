"""Checks for the saved-run and read-only dashboard interfaces."""
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from agenthon_quant import trading
from agenthon_quant.onboarding import bundle_run, example_path
from agenthon_quant.records import execute, reproduce, write_json
from agenthon_quant.spectral import METHOD_ID, spectral_profile
from scripts.edge_lab_spectral import render


class SpectralWorkflowTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        example = example_path("historical")
        self.spec = json.loads(example.read_text())
        self.prices = self.root / "session.csv"
        shutil.copyfile(example.parent / self.spec["data"], self.prices)
        self.spec["data"] = self.prices.name

    def calculate(self, name, **settings):
        path = self.root / f"{name}.json"
        write_json(path, {**self.spec, **settings})
        return execute(path, self.root / name)

    def test_trades_metrics_and_artifact_provenance(self):
        # Observe the actual simulator outputs from both normal run invocations.
        ledgers = []
        simulate = trading.simulate_ledger
        def capture(*args):
            ledger = simulate(*args)
            ledgers.append(ledger)
            return ledger
        with patch.object(trading, "simulate_ledger", side_effect=capture):
            baseline = self.calculate("baseline")
            enabled = self.calculate("enabled", spectral_diagnostic=True)
        self.assertEqual((baseline["status"], enabled["status"]), ("passed", "passed"))
        self.assertEqual(len(ledgers), 12)
        self.assertEqual(ledgers[:6], ledgers[6:])
        self.assertEqual(baseline["analysis"]["results"], enabled["analysis"]["results"])
        self.assertEqual(baseline["analysis"]["checks"], enabled["analysis"]["checks"])
        self.assertEqual((self.root/"baseline/validated-results.json").read_bytes(),
                         (self.root/"enabled/validated-results.json").read_bytes())
        self.assertFalse((self.root/"baseline/spectral.json").exists())
        folder = self.root / "enabled"
        raw = (folder / "spectral.json").read_bytes()
        artifact = json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), enabled["output_artifacts_sha256"]["spectral.json"])
        self.assertEqual(artifact["input_sha256"], hashlib.sha256(self.prices.read_bytes()).hexdigest())
        self.assertEqual(artifact["effective_specification_sha256"], enabled["effective_specification_sha256"])
        self.assertEqual(artifact["source_fingerprint_sha256"], enabled["code"]["source_fingerprint_sha256"])
        self.assertEqual(artifact["method_id"], METHOD_ID)
        self.assertEqual(artifact["price_adjustment"], "unadjusted")
        self.assertIn("excluding cash distributions", artifact["return_basis"])
        rows = artifact["observations"]
        with self.prices.open() as handle:
            prices = list(csv.DictReader(handle))
        self.assertEqual([r["date"] for r in rows], [p["SessionUTC"] for p in prices])
        self.assertEqual([r["status"] for r in rows], ["warmup"]*64 + ["ok"]*27)
        self.assertTrue(all(r["spectral_entropy"] is None for r in rows[:64]))
        closes = [float(p["LastTradeClose"]) for p in prices]
        returns = [math.log(b / a) for a, b in zip(closes, closes[1:])]
        for i in (64, 90):
            expected = spectral_profile(returns[i-64:i])
            self.assertAlmostEqual(rows[i]["spectral_entropy"], expected["spectral_entropy"], places=12)
            self.assertEqual(rows[i]["dominant_period_observations"], expected["dominant_period_observations"])
        self.prices.unlink()
        self.assertEqual(reproduce(folder, self.root/"replay")["status"], "passed")
        self.assertEqual(raw, (self.root/"replay/spectral.json").read_bytes())
        archive = self.root/"verified.zip"
        bundle_run(folder, archive)
        with ZipFile(archive) as zipped:
            self.assertEqual(raw, zipped.read("spectral.json"))

    def test_boolean_and_constant_windows(self):
        for i, value in enumerate((1, "false", None, {})):
            record = self.calculate(f"invalid{i}", spectral_diagnostic=value)
            self.assertEqual(record["status"], "invalid")
            self.assertIn("JSON boolean", record["error"])
        with self.prices.open() as handle:
            rows = list(csv.DictReader(handle))
        with self.prices.open("w") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            for r in rows:
                writer.writerow({**r, "FirstTradeOpen": 100, "LastTradeClose": 100})
        self.assertEqual(self.calculate("off", spectral_diagnostic=False)["status"], "passed")
        self.assertFalse((self.root/"off/spectral.json").exists())
        self.assertEqual(self.calculate("flat", spectral_diagnostic=True)["status"], "passed")
        obs = json.loads((self.root/"flat/spectral.json").read_bytes())["observations"]
        self.assertTrue(all(r["status"] == "no_variation" and r["spectral_entropy"] is None
                            and r["dominant_period_observations"] is None for r in obs[64:]))

    def test_dashboard_reads_only_verified_artifact(self):
        self.calculate("enabled", spectral_diagnostic=True)
        run = self.root/"enabled"
        source = self.root/"dashboard.html"
        source.write_text('<main><footer></footer></main><script id="dashboard-data"></script>')
        original = source.read_bytes()
        out = self.root/"preview.html"
        render(source, run, out)
        self.assertIn("2025-06-30", out.read_text())
        self.assertIn("trading observations", out.read_text())
        self.assertEqual(source.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            render(source, run, source)
        (run/"spectral.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash"):
            render(source, run, self.root/"second.html")
        with self.assertRaisesRegex(ValueError, "hash"):
            bundle_run(run, self.root/"corrupt.zip")

    def test_failed_spectral_publication_cleans_validated_outputs(self):
        def failing(path, value):
            if path.name == "spectral.json":
                raise OSError("diagnostic write failed")
            write_json(path, value)
        with patch("agenthon_quant.records.write_json", side_effect=failing):
            record = self.calculate("failed", spectral_diagnostic=True)
        self.assertEqual(record["status"], "failed")
        self.assertFalse((self.root/"failed/validated-results.json").exists())
        self.assertFalse((self.root/"failed/spectral.json").exists())
        self.assertNotIn("output_artifacts_sha256", record)
