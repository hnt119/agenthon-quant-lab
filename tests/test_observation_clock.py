"""The dated public clock and read-only hosted rehearsal for the weekly observation."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("paper_run", ROOT / "observations/run_job.py")
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)
MONDAY = datetime(2031, 1, 6, 0, 7, tzinfo=UTC)


def wrapper(schedule):
    repo = {"full_name": job.REPO, "private": False, "visibility": "public"}
    clock = {"status": "completed", "event": "schedule", "conclusion": "success",
             "run_attempt": 1, "head_branch": "main", "path": ".github/workflows/paper-clock.yml",
             "head_repository": repo.copy(), "repository": repo.copy(), "head_sha": "1"*40,
             "created_at": MONDAY.isoformat(), "display_title": "Paper allocation clock / " + schedule}
    return {"action": "completed", "repository": repo, "workflow_run": clock}


class ClockTests(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.event = Path(temp.name) / "event.json"
        self.env = dict(GITHUB_EVENT_NAME="workflow_run", GITHUB_ACTIONS="true",
                        GITHUB_REPOSITORY=job.REPO, GITHUB_RUN_ATTEMPT="1",
                        GITHUB_REF="refs/heads/main", RUNNER_ENVIRONMENT="github-hosted",
                        GITHUB_EVENT_PATH=str(self.event))

    def load_event(self, payload, **kwargs):
        self.event.write_text(json.dumps(payload))
        return job.phase_from_event(self.env, kwargs.pop("at", MONDAY), **kwargs)

    def test_clock_phases_private_unknown_and_old_week(self):
        for schedule, phase in job.SCHEDULES.items():
            payload = wrapper(schedule)
            self.assertEqual(self.load_event(payload), phase)
            with self.assertRaisesRegex(ValueError, "Expired"):
                self.load_event(payload, at=MONDAY+timedelta(days=7))
        for path, key, value in (("repository", "visibility", None),("repository","private",True),
                                 ("repository","private",None),("workflow_run","path","another.yml"),
                                 ("workflow_run","run_attempt",2),("workflow_run","head_repository",{}),
                                 ("workflow_run","head_branch","from-fork"),
                                 ("workflow_run","display_title","7 0 * * 1")):
            with self.subTest(key=key):
                payload = wrapper("7 0 * * 1")
                if value is None:
                    del payload[path][key]
                else:
                    payload[path][key] = value
                with self.assertRaises(ValueError):
                    self.load_event(payload)

    def test_rehearsal_cannot_observe_and_production_cannot_rehearse(self):
        payload = wrapper("workflow_dispatch")
        payload["workflow_run"]["event"] = "workflow_dispatch"
        with self.assertRaises(ValueError):
            self.load_event(payload)
        self.assertEqual(self.load_event(payload, rehearsal=True), "rehearsal")
        with self.assertRaises(ValueError):
            self.load_event(wrapper("41 0 * * 1"), rehearsal=True)
        for field, value in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_REF","refs/pull/1/head"),
                             ("RUNNER_ENVIRONMENT","self-hosted"),("GITHUB_REPOSITORY","another/repo"),
                             ("GITHUB_EVENT_NAME","workflow_dispatch")):
            self.event.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                job.phase_from_event({**self.env, field:value}, MONDAY, rehearsal=True)

    @skipUnless(os.environ.get("PAPER_HOSTED_REHEARSAL") == "1", "requires hosted manual clock evidence")
    def test_actual_hosted_clock_and_public_source_against_disposable_registration(self):
        from observations import recorder

        self.assertEqual(job.phase_from_event(os.environ, rehearsal=True), "rehearsal")
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            job.phase_from_event(os.environ)
        run = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())["workflow_run"]
        sha = job.git(ROOT, "rev-parse", "HEAD")
        self.assertEqual(sha, run["head_sha"])
        protocol_raw = (ROOT / "observations/protocol.json").read_bytes()
        deadline = datetime.fromisoformat(json.loads(protocol_raw)["registration_deadline"])
        with TemporaryDirectory() as td:
            state = Path(td)
            job.git(state, "init", "-q", "-b", job.BRANCH)
            job.git(state, "remote", "add", "origin", "https://github.com/" + job.REPO)
            reg = {"revision": sha, "protocol_sha256": sha256(protocol_raw).hexdigest(),
                   "registered_at": (deadline - timedelta(days=1)).isoformat(), "scope": "rehearsal"}
            (state/"registration.json").write_text(json.dumps(reg))
            recorder.Journal(state, json.loads(protocol_raw)).save_status()
            job.git(state, "add", "registration.json", "status.json")
            job.git(state, "-c", "user.name=synthetic", "-c", "user.email=fixture@example.org",
                    "commit", "-m", "Temporary qualification fixture")
            qualified = job.registered(ROOT, state, sha)
            job.state_files(state, qualified["limits"]["max_state_bytes"])
            self.assertEqual(recorder.validate(state, qualified)["completed"], 0)
