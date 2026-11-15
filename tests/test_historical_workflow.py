"""Exercise the same file, report and replay contract used by the installed skill."""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

from agenthon_quant.cli import main
from agenthon_quant.onboarding import bundle_run, example_path
from agenthon_quant.records import execute, reproduce, write_json


class HistoricalWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        example = example_path("historical")
        self.spec = json.loads(example.read_text())
        self.data = self.root / "prices.csv"
        shutil.copyfile(example.parent / self.spec["data"], self.data)
        self.spec["data"] = self.data.name
        self.request = self.root / "research.json"
        write_json(self.request, self.spec)
        self.out = self.root / "run"

    def test_inspect_only_market_fields_and_identity(self):
        minimal = {field: self.spec[field] for field in ("data", "columns", "source", "price_adjustment")}
        write_json(self.request, minimal)
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            self.assertEqual(main(["inspect-data", str(self.request)]), 0)
        quality = json.loads(capture.getvalue())
        self.assertEqual(quality["observation_count"], 91)
        self.assertEqual(quality["input_sha256"], hashlib.sha256(self.data.read_bytes()).hexdigest())
        self.assertEqual(quality["calendar_gaps"]["interval_count"], 0)

    def test_replay_without_original_and_deliberate_cost_change(self):
        first = execute(self.request, self.out)
        self.assertEqual(first["status"], "passed", first.get("error"))
        self.request.unlink()
        self.data.unlink()
        exact = reproduce(self.out, self.root / "repeat")
        self.assertEqual(exact["analysis"], first["analysis"])
        changed = reproduce(self.out, self.root / "changed", {"fee_bps": 20})
        self.assertEqual(changed["status"], "passed")
        self.assertEqual(changed["derived_from"]["changes"], {"fee_bps": 20})
        old = first["analysis"]["results"]["strategies"]["sma"]
        new = changed["analysis"]["results"]["strategies"]["sma"]
        self.assertEqual(new["gross"], old["gross"])
        self.assertLess(new["net"]["metrics"]["ending_equity"], old["net"]["metrics"]["ending_equity"])

    def test_bundle_contains_readable_report_and_exact_daily_paths(self):
        record = execute(self.request, self.out)
        zipped = self.root / "research.zip"
        bundle_run(self.out, zipped)
        with zipfile.ZipFile(zipped) as bundle:
            results = json.loads(bundle.read("validated-results.json"))
            periods = results["strategies"]["cash"]["net"]["periods"]
            curves = list(csv.DictReader(io.StringIO(bundle.read("equity-drawdown.csv").decode())))
            self.assertEqual(len(curves), 91 * 3 * 2)
            for row in curves:
                i = results["dates"].index(row["date"])
                book = results["strategies"][row["strategy"]][row["treatment"]]
                self.assertEqual(float(row["equity"]), book["equity"][i])
                self.assertEqual(float(row["drawdown_fraction"]), book["drawdown"][i])
                self.assertLessEqual(periods[row["period"]]["start"], row["date"])
                self.assertGreaterEqual(periods[row["period"]]["end"], row["date"])
            svg = ET.fromstring(bundle.read("equity-drawdown.svg"))
            self.assertEqual(len(svg.findall(".//{http://www.w3.org/2000/svg}polyline")), 6)
            self.assertIn(b"After-cost comparison", bundle.read("report.md"))
            for name, hash_ in record["output_artifacts_sha256"].items():
                self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), hash_)
        (self.out / "equity-drawdown.svg").write_text("altered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            bundle_run(self.out, self.root / "altered.zip")

    def test_failed_report_publication_removes_curves(self):
        write = Path.write_bytes
        def fail_svg(path, content):
            if path.name == "equity-drawdown.svg":
                raise OSError("disk write rejected")
            return write(path, content)
        with patch.object(Path, "write_bytes", fail_svg):
            record = execute(self.request, self.out)
        self.assertEqual(record["status"], "failed")
        for name in ("validated-results.json", "equity-drawdown.csv", "equity-drawdown.svg"):
            self.assertFalse((self.out / name).exists())
        self.assertIn("disk write rejected", (self.out / "report.md").read_text())
        self.assertNotIn("](equity-drawdown.svg)", (self.out / "report.md").read_text())

    def test_invalid_market_data_explanation_can_be_bundled(self):
        with self.data.open("a") as handle:
            handle.write("2025-06-30,1,2\n")
        result = execute(self.request, self.out)
        self.assertEqual(result["status"], "invalid")
        self.assertIn("duplicate session", result["error"])
        output = self.root / "diagnosis.zip"
        bundle_run(self.out, output)
        with zipfile.ZipFile(output) as bundle:
            self.assertIn("inputs/data.csv", bundle.namelist())
            self.assertNotIn("validated-results.json", bundle.namelist())

    def test_parquet_run_uses_same_normalized_prices(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("Parquet extra unavailable")
        csv_result = execute(self.request, self.out)["analysis"]["results"]
        with self.data.open() as handle:
            rows = list(csv.DictReader(handle))
        dates, opens, closes = (
            self.spec["columns"][field] for field in ("date", "open", "close"))
        table = pa.table({dates: [row[dates] for row in rows],
                          opens: [float(row[opens]) for row in rows], closes: [float(row[closes]) for row in rows]})
        pq.write_table(table, self.root / "prices.pq")
        write_json(self.request, {**self.spec, "data": "prices.pq"})
        parquet = execute(self.request, self.root / "parquet")
        self.assertEqual(parquet["status"], "passed", parquet.get("error"))
        result = parquet["analysis"]["results"]
        self.assertEqual(result["dates"], csv_result["dates"])
        self.assertEqual(result["strategies"], csv_result["strategies"])
        self.assertNotEqual(result["quality"]["input_sha256"], csv_result["quality"]["input_sha256"])
