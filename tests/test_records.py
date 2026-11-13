import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agenthon_quant.cli import main
from agenthon_quant.records import execute, reproduce, strict_json, verify_saved, write_json


BASE = {"workflow": "options", "spot": 100, "strike": 100, "maturity_years": 1,
        "volatility": 0.2, "rate": 0.05, "dividend_yield": 0.0, "currency": "USD", "option_type": "both"}


class RecordTests(unittest.TestCase):
    def test_duplicate_nonfinite_json(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json(raw)

    def test_save_reproduce_change_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "options.json", BASE)
            first = execute(root / "options.json", root / "first")
            self.assertEqual(first["status"], "passed", first)
            self.assertTrue((root / "first/validated-results.json").is_file())
            second = reproduce(root / "first", root / "second")
            self.assertEqual(first["analysis"], second["analysis"])
            changed = reproduce(root / "first", root / "changed", {"volatility": 0.3})
            self.assertNotEqual(first["analysis"]["results"], changed["analysis"]["results"])
            self.assertEqual(changed["derived_from"]["changes"], {"volatility": 0.3})
            (root / "first/spec.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "specification"):
                verify_saved(root / "first")

    def test_snapshot_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "spec.json", BASE)
            execute(root / "spec.json", root / "run")
            (root / "run/inputs/request.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                reproduce(root / "run", root / "new")
            self.assertFalse((root / "new").exists())

    def test_invalid_run_saved_and_existing_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.json").write_text('{"workflow":"options","volatility":-1}')
            result = execute(root / "bad.json", root / "run")
            self.assertEqual(result["status"], "invalid")
            self.assertTrue((root / "run/report.md").is_file())
            self.assertFalse((root / "run/validated-results.json").exists())
            with self.assertRaises(FileExistsError):
                execute(root / "bad.json", root / "run")

    def test_overflow_and_bad_json_still_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i, raw in enumerate(('{"spot":1e999}', '{oops', '[]')):
                path = root / f"bad{i}.json"
                path.write_text(raw)
                result = execute(path, root / f"run{i}")
                self.assertEqual(result["status"], "invalid")
                json.loads((root / f"run{i}/run.json").read_text())

    def test_cli_explanation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "bad.json", {"workflow": "unsupported"})
            self.assertEqual(main(["run", str(root / "bad.json"), "--out", str(root / "run")]), 2)
            self.assertEqual(main(["explain", str(root / "run")]), 0)

    def test_publication_failure_never_leaves_passed_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "spec.json", BASE)
            original_writer = write_json
            def fail_output(path, value):
                if path.name == "validated-results.json":
                    raise OSError("deliberate output write failure")
                original_writer(path, value)
            with patch("agenthon_quant.records.write_json", side_effect=fail_output):
                result = execute(root / "spec.json", root / "run")
            saved = strict_json((root / "run/run.json").read_bytes())
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(result["status"], "failed")
            self.assertFalse((root / "run/validated-results.json").exists())
            self.assertIn("Artifact publication failed", (root / "run/report.md").read_text())
