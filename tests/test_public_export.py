import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("export_site", ROOT / "scripts/export_site.py")
export = importlib.util.module_from_spec(loader)
loader.loader.exec_module(export)


class PublicExportTests(unittest.TestCase):
    def test_projection_is_deterministic_and_crosslinked(self):
        a, b = export.projection(), export.projection()
        self.assertEqual(export.encoded(a), export.encoded(b))
        self.assertGreaterEqual(len(a["papers"]), 12)
        self.assertTrue(any(e["status"] == "not_run" for e in a["experiments"]))
        self.assertTrue(any(e["status"] == "incomplete" for e in a["experiments"]))

    def test_private_payload_and_local_paths_rejected(self):
        for value in ({"api_key": "anything"}, {"path": "/Users/example/private.csv"}, {"x": "http://localhost:3000"}):
            with self.assertRaises(ValueError):
                export.public_value(value)

    def test_dangling_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("research", "experiments"):
                (root / name).mkdir()
            papers = json.loads((ROOT / "research/papers.json").read_text())
            papers["papers"][0]["experiment_ids"] = ["nonexistent"]
            (root / "research/papers.json").write_text(json.dumps(papers))
            (root / "experiments/experiments.json").write_bytes((ROOT / "experiments/experiments.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "unknown experiment"):
                export.projection(root)
