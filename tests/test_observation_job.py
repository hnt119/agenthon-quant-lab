"""Synthetic schedule and persistence checks. No provider or GitHub calls."""
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("paper_job", ROOT / "observations/run_job.py")
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


class JobTests(TestCase):
    def test_witness_and_receipt_cutoffs(self):
        fixing = datetime(2031, 1, 6, 0, 45, tzinfo=UTC)
        for delta, final_secs, accepted in ((-240, 75, True), (-1, 300, True), (0, 75, False),
                                           (-2, 301, False), (-400, 75, False)):
            waits = []
            self.assertEqual(job.fill_window(fixing + timedelta(seconds=delta),
                                             lambda: fixing + timedelta(seconds=final_secs),
                                             waits.append), accepted)
            if waits:
                self.assertEqual(waits, [75 - delta])
                self.assertLessEqual(waits[0], 390)
        self.assertFalse(job.fill_window(fixing + timedelta(days=1), lambda:fixing, self.fail))

    def test_bound_counts_http_requests_before_read_even_on_failure(self):
        clock = datetime(2031, 1, 6, tzinfo=UTC)
        def stale(event, count):
            raise RuntimeError("unavailable")
        closes, quote = job.metered_source(stale, lambda event: 5, 3, clock + timedelta(days=1),
                                          lambda: clock)
        with self.assertRaises(RuntimeError):
            closes(clock, count=21)
        self.assertEqual(quote(clock), 5)
        with self.assertRaisesRegex(ValueError, "budget"):
            quote(clock)
        _, late = job.metered_source(stale, self.fail, 3, clock, lambda: clock)
        with self.assertRaisesRegex(ValueError, "horizon"):
            late(clock)

    def test_size_ceiling_and_file_allowlist(self):
        with TemporaryDirectory() as td:
            d = Path(td)
            (d/"events").mkdir()
            (d/"events/00001.json").write_bytes(b"12345")
            job.state_files(d, 5)
            with self.assertRaises(ValueError):
                job.state_files(d, 4)
            (d/"events/00002.json").symlink_to(d/"events/00001.json")
            with self.assertRaises(ValueError):
                job.state_files(d, 50)

    def test_local_remote_replay_race_and_preserved_events(self):
        with TemporaryDirectory() as td:
            base = Path(td)
            bare, state = base/"remote.git", base/"state"
            subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
            subprocess.run(["git", "init", "-q", "-b", job.BRANCH, str(state)], check=True)
            def commit(message):
                job.git(state, "-c", "user.name=fixture", "-c", "user.email=test@example.org",
                        "commit", "-m", message)
            job.git(state, "remote", "add", "origin", str(bare))
            (state/"registration.json").write_text("{}\n")
            job.git(state, "add", "registration.json")
            commit("synthetic seed")
            job.git(state, "push", "origin", "HEAD:refs/heads/" + job.BRANCH)
            (state/"events").mkdir()
            event = state/"events/00001.json"
            event.write_text('{"kind":"synthetic"}\n')
            (state/"status.json").write_text("{}\n")
            head = job.publish(state, "marks")
            self.assertEqual(job.publish(state, "marks"), head)
            self.assertEqual(job.git(state, "rev-list", "--count", "HEAD"), "2")
            event.write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "Existing evidence"):
                job.publish(state, "marks")
            job.git(state, "restore", "events/00001.json")
            (state/"status.json").write_text('{"test":true}\n')
            job.git(state, "add", "status.json")
            commit("synthetic divergent checkout")
            with self.assertRaisesRegex(ValueError, "diverged"):
                job.remote_witness(state)
