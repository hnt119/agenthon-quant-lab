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


    def test_programme_traces_four_comparisons_to_three_frozen_runs(self):
        view = export.programme_projection()
        studies = view["studies"]
        self.assertEqual(len(studies), 6)
        completed = [s for s in studies if s["execution_state"] == "completed"]
        self.assertEqual({s["id"] for s in completed}, {"btc-momentum", "btc-fft-gate", "cost-break-even", "turnover-aware"})
        parent = [s for s in completed if s["id"] in {"btc-momentum", "btc-fft-gate"}]
        self.assertEqual(len({s["source_receipt_url"] for s in parent}), 1)
        cost = next(s for s in completed if s["id"] == "cost-break-even")
        self.assertEqual(cost["experiment_id"], "btc-cost-break-even-v1")
        self.assertNotEqual(cost["source_receipt_url"], parent[0]["source_receipt_url"])
        self.assertEqual(cost["evaluation_period"], parent[0]["evaluation_period"])
        weekly = next(s for s in completed if s["id"] == "turnover-aware")
        self.assertEqual(weekly["experiment_id"], "btc-weekly-cadence-v1")
        self.assertEqual(len({s["source_receipt_url"] for s in completed}), 3)
        self.assertEqual(weekly["evaluation_period"], parent[0]["evaluation_period"])
        self.assertEqual(export.study_export(weekly["experiment_id"]),
                         (ROOT / "site-export/btc-weekly-cadence.json").read_bytes())
        protocol = json.loads((ROOT / "experiments/btc-financial-v1/protocol.json").read_bytes())
        years = protocol["evaluation_years"]
        for study in parent:
            self.assertEqual(study["experiment_id"], protocol["id"])
            self.assertEqual(study["evaluation_period"], [f"{min(years)}-01-01", f"{max(years)}-12-31"])
        self.assertEqual(view["provenance"]["canonical_files_sha256"]["research/programme.json"],
                         export.sha((ROOT / "research/programme.json").read_bytes()))

    def test_proposed_study_cannot_publish_a_finding_or_unknown_dependency(self):
        catalogue = json.loads((ROOT / "research/programme.json").read_bytes())
        proposed = next(s for s in catalogue["studies"] if s["execution_state"] == "proposed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research").mkdir()
            for field, value in [("finding", "Profitable"), ("dependencies", ["unknown"]), ("private_key", "x")]:
                mutated = {**proposed, "dependencies": [], field: value}
                (root / "research/programme.json").write_text(json.dumps({"schema_version": 1, "studies": [mutated]}))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    export.programme_projection(root)

    def test_cost_exhibit_requires_exact_reviewed_payload(self):
        self.assertEqual(export.cost_study_export(), (ROOT / "site-export/btc-cost-break-even.json").read_bytes())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = Path("reports/btc-cost-break-even-v1")
            (root / folder).mkdir(parents=True)
            (root / folder / "run.json").write_bytes((ROOT / folder / "run.json").read_bytes())
            (root / folder / "public.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "differs from the qualified study"):
                export.cost_study_export(root)

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

    def test_numerical_corpus_allows_only_bounded_rounding_and_preserves_checks(self):
        import copy
        current = export.numerical_reference()
        for mutation in ("schema_bool", "input_bool", "price_bool"):
            bad = copy.deepcopy(current)
            if mutation == "schema_bool":
                bad["schema_version"] = True
            elif mutation == "input_bool":
                bad["cases"][0]["inputs"]["years"] = True
            else:
                bad["cases"][1]["expected"]["call"] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                export.check_reference(bad, current)
        saved = copy.deepcopy(current)
        saved["cases"][0]["expected"]["call"] += 1e-12
        self.assertEqual(len(export.check_reference(saved, current)), 1)
        saved["cases"][0]["expected"]["call"] += .001
        with self.assertRaises(ValueError):
            export.check_reference(saved, current)
        for field in ("id", "inputs"):
            bad = copy.deepcopy(current)
            bad["cases"][0][field] = "changed"
            with self.assertRaises(ValueError):
                export.check_reference(bad, current)
        bad = copy.deepcopy(current)
        bad["reference_source_sha256"] = "changed"
        with self.assertRaises(ValueError):
            export.check_reference(bad, current)
        bad = copy.deepcopy(current)
        bad["cases"][0]["python_check_counts"]["passed"] -= 1
        bad["cases"][0]["python_check_counts"]["unavailable"] += 1
        with self.assertRaises(ValueError):
            export.check_reference(bad, current)
        bad = copy.deepcopy(current)
        bad["cases"][0]["python_check_counts"]["failed"] = 1
        with self.assertRaises(ValueError):
            export.check_reference(bad, current)


