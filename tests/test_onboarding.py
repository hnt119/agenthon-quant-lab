import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from agenthon_quant.archive import search_archive
from agenthon_quant.cli import main
from agenthon_quant.onboarding import bundle_run, doctor, example_path, install_skill, setup_environment
from agenthon_quant.records import digest, execute, write_json

ROOT = Path(__file__).resolve().parents[1]


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def make_skill(self):
        target = self.root / "checkout/skills/quant-research"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("test skill")
        return self.root / "checkout", self.root / "skills"

    def test_skill_link_idempotent_and_existing_destinations_preserved(self):
        checkout, destination = self.make_skill()
        first = install_skill(checkout, destination)
        self.assertEqual(first["status"], "linked")
        self.assertEqual(install_skill(checkout, destination)["status"], "already_linked")
        link = destination / "quant-research"
        link.unlink()
        link.write_text("keep this existing skill")
        with self.assertRaisesRegex(ValueError, "preserved"):
            install_skill(checkout, destination)
        self.assertEqual(link.read_text(), "keep this existing skill")
        link.unlink()
        other = self.root / "other"
        other.mkdir()
        link.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "preserved"):
            install_skill(checkout, destination)
        self.assertEqual(link.resolve(), other)

    def test_setup_uses_only_checkout_venv_and_argv_commands(self):
        checkout, _ = self.make_skill()
        (checkout / "pyproject.toml").write_text("[project]\nname='test'\n")
        (checkout / "requirements-verified.txt").write_text("scipy==1.18.1\n")
        commands = []
        def run(command, **kwargs):
            commands.append(command)
            self.assertIs(kwargs["shell"], False)
            self.assertTrue(kwargs["check"])
            self.assertEqual(kwargs["cwd"], checkout)
            if command[1:3] == ["-m", "venv"]:
                environment = Path(command[3])
                (environment / "bin").mkdir(parents=True)
                (environment / "pyvenv.cfg").write_text("home=test\n")
                (environment / "bin/python").write_text("test placeholder")
        result = setup_environment(checkout, runner=run)
        self.assertEqual(result["commands_completed"], 3)
        self.assertEqual(commands[1][0], str(checkout / ".venv/bin/python"))
        self.assertEqual(commands[1][2:5], ["pip", "install", "-r"])
        self.assertEqual(commands[2][-1], "--no-deps")
        commands.clear()
        setup_environment(checkout, runner=run)
        self.assertEqual(len(commands), 2)

    def test_setup_preserves_invalid_existing_venv_and_stops_on_failure(self):
        checkout, _ = self.make_skill()
        (checkout / "pyproject.toml").write_text("test")
        (checkout / "requirements-verified.txt").write_text("test")
        (checkout / ".venv").write_text("unrelated file")
        with self.assertRaisesRegex(ValueError, "preserved"):
            setup_environment(checkout, runner=lambda *a, **k: self.fail("must not execute"))
        self.assertEqual((checkout / ".venv").read_text(), "unrelated file")
        (checkout / ".venv").unlink()
        def fail(command, **kwargs):
            raise subprocess.CalledProcessError(1, command)
        with self.assertRaisesRegex(ValueError, "No system-Python fallback"):
            setup_environment(checkout, runner=fail)

    def test_doctor_distinguishes_required_and_optional_dependencies(self):
        def version(package):
            if package == "pyarrow":
                from importlib.metadata import PackageNotFoundError
                raise PackageNotFoundError(package)
            return {"scipy": "1.18.1", "numpy": "2.5.4"}[package]
        with patch("agenthon_quant.onboarding.importlib.metadata.version", side_effect=version):
            result = doctor(ROOT, skills_dir=self.root / "skills")
        self.assertEqual(result["status"], "ready")
        optional = next(c for c in result["checks"] if c["name"] == "pyarrow")
        self.assertEqual(optional["status"], "unavailable")
        with patch("agenthon_quant.onboarding.importlib.metadata.version", return_value="9.0.0"):
            self.assertEqual(doctor(ROOT)["status"], "needs_setup")

    def test_example_resolves_from_unrelated_cwd(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(example_path("options"), ROOT / "examples/options.json")
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(["example", "options", "--out", str(self.root / "example")])
            self.assertEqual(status, 0)
            self.assertTrue((self.root / "example/report.md").is_file())
        finally:
            os.chdir(previous)

    def test_archive_search_is_local_case_insensitive_and_status_specific(self):
        (self.root / "research").mkdir()
        (self.root / "experiments").mkdir()
        write_json(self.root / "research/papers.json", {"papers": [
            {"id": "p1", "title": "Option Paper", "adaptation_status": "implemented", "topics": ["Pricing"]},
            {"id": "p2", "title": "FFT hypothesis", "adaptation_status": "deferred"}]})
        write_json(self.root / "experiments/experiments.json", {"experiments": [
            {"id": "e1", "title": "Negative result", "status": "failed", "hypothesis": "Latency"},
            {"id": "e2", "title": "Not run", "status": "not_run"}]})
        self.assertEqual([r["id"] for r in search_archive(self.root, "papers", "PRICING", "IMPLEMENTED")], ["p1"])
        self.assertEqual([r["id"] for r in search_archive(self.root, "experiments", "latency", "failed")], ["e1"])
        self.assertEqual(search_archive(self.root, "papers", "no match"), [])
        with patch("agenthon_quant.onboarding.repository_root", return_value=self.root), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["archive", "papers", "pricing", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["count"], 1)

    def make_run(self):
        out = self.root / "run"
        execute(ROOT / "examples/options.json", out)
        return out

    def test_bundle_contains_verified_allowlist_and_manifest(self):
        run = self.make_run()
        (run / "unrelated-private.txt").write_text("never bundle arbitrary neighbors")
        target = self.root / "run.zip"
        receipt = bundle_run(run, target)
        self.assertEqual(receipt["intended_visibility"], "private")
        with zipfile.ZipFile(target) as archive:
            self.assertNotIn("unrelated-private.txt", archive.namelist())
            manifest = json.loads(archive.read("bundle-manifest.json"))
            self.assertTrue(manifest["contains_input_data"])
            for name, identity in manifest["files"].items():
                self.assertEqual(digest(archive.read(name)), identity["sha256"])
        original = target.read_bytes()
        with self.assertRaisesRegex(ValueError, "preserved"):
            bundle_run(run, target)
        self.assertEqual(target.read_bytes(), original)

    def test_bundle_rejects_tampering_and_symlink_snapshot(self):
        run = self.make_run()
        snapshot = run / "inputs/request.json"
        original = snapshot.read_bytes()
        snapshot.write_bytes(original + b" ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            bundle_run(run, self.root / "bad.zip")
        self.assertFalse((self.root / "bad.zip").exists())
        snapshot.unlink()
        external = self.root / "external.json"
        external.write_bytes(original)
        snapshot.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle_run(run, self.root / "link.zip")
        self.assertFalse((self.root / "link.zip").exists())

    def test_bundle_rejects_changed_results(self):
        run = self.make_run()
        results = json.loads((run / "validated-results.json").read_text())
        results["valuations"]["call"]["price"] += 1
        write_json(run / "validated-results.json", results)
        with self.assertRaisesRegex(ValueError, "do not match"):
            bundle_run(run, self.root / "bad-results.zip")

    def test_bundle_preserves_run_and_rejects_symlink_root(self):
        run = self.make_run()
        before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "outside the saved run"):
            bundle_run(run, run / "extra.zip")
        alias = self.root / "run-alias"
        alias.symlink_to(run, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink run directory"):
            bundle_run(alias, self.root / "alias.zip")
        after = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_doctor_reports_broken_binary_import(self):
        with patch("agenthon_quant.onboarding.importlib.import_module", side_effect=OSError("binary unavailable")):
            result = doctor(ROOT, skills_dir=self.root / "skills")
        self.assertEqual(result["status"], "needs_setup")
        self.assertTrue(any(c["status"] == "failed" and "import failed" in c["details"] for c in result["checks"]))
