"""Entrypoint for the registered schedule. Rehearsals call recorder.run separately."""
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from time import sleep

REPO = "hnt119/agenthon-quant-lab"
BRANCH = "observations/weekly-allocation-v1"
SCHEDULES = {"7 0 * * 1": "decision", "41 0 * * 1": "fill", "17 3 * * *": "marks"}
EVENT = re.compile(r"events/[0-9]{5}\.json")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, timeout=30,
                          capture_output=True, text=True).stdout.rstrip("\n")


def remote_witness(state):
    """A freshly fetched remote head must equal the clean or newly committed local head."""
    ref = "refs/heads/" + BRANCH
    local = git(state, "rev-parse", "HEAD")
    require(git(state, "ls-remote", "--exit-code", "origin", ref) == f"{local}\t{ref}",
            "Public record head diverged; stop without a retry")
    return local


def registered(code, state, revision):
    require(re.fullmatch(r"[a-f0-9]{40}", revision) and git(code, "rev-parse", "HEAD") == revision,
            "Registered source revision differs")
    for checkout in (code, state):
        require(git(checkout, "status", "--porcelain", "--untracked-files=all") == "", "Dirty checkout")
        remote = git(checkout, "remote", "get-url", "origin")
        require(remote.removesuffix(".git") == f"https://github.com/{REPO}", "Unexpected Git remote")
    require(git(state, "symbolic-ref", "--short", "HEAD") == BRANCH, "Unexpected evidence branch")
    registration = json.loads((state / "registration.json").read_bytes())
    protocol_raw = (code / "observations/protocol.json").read_bytes()
    require(registration["revision"] == revision and
            registration["protocol_sha256"] == sha256(protocol_raw).hexdigest(), "Registration mismatch")
    protocol = json.loads(protocol_raw)
    registered_at = datetime.fromisoformat(registration["registered_at"])
    deadline = datetime.fromisoformat(protocol["registration_deadline"])
    require(registered_at.utcoffset() == timedelta(0) and registered_at < deadline, "Late registration")
    return protocol


def phase_from_event(env, at=None, *, rehearsal=False):
    """Bind a completed clock run to its creation date. A late Monday cannot become next Monday."""
    at = at or datetime.now(UTC)
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_EVENT_NAME") == "workflow_run" and
            env.get("GITHUB_REPOSITORY") == REPO and env.get("GITHUB_REF") == "refs/heads/main" and
            env.get("GITHUB_RUN_ATTEMPT") == "1" and env.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Expected original hosted workflow-run event")
    payload = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_bytes())
    repo = payload.get("repository", {})
    clock = payload.get("workflow_run", {})
    require(repo.get("full_name") == REPO and repo.get("private") is False and
            repo.get("visibility") == "public" and payload.get("action") == "completed" and
            clock.get("status") == "completed" and clock.get("conclusion") in ("success", "skipped") and
            clock.get("path") == ".github/workflows/paper-clock.yml" and clock.get("head_branch") == "main" and
            clock.get("run_attempt") == 1 and clock.get("head_repository", {}).get("full_name") == REPO and
            clock.get("repository", {}).get("full_name") == REPO and
            re.fullmatch("[a-f0-9]{40}", clock.get("head_sha", "")), "Untrusted public clock identity")
    created = datetime.fromisoformat(clock["created_at"])
    require(created.utcoffset() == timedelta(0) and created.date() == at.date() and
            timedelta(0) <= at-created < timedelta(hours=12), "Expired or future clock tick")
    prefix = "Paper allocation clock / "
    title = clock.get("display_title", "")
    if rehearsal:
        require(clock["event"] == "workflow_dispatch" and title == prefix + "workflow_dispatch",
                "Expected qualification-only manual clock")
        return "rehearsal"
    schedule = title.removeprefix(prefix)
    require(clock["event"] == "schedule" and title.startswith(prefix) and schedule in SCHEDULES,
            "Unregistered clock event or schedule")
    phase = SCHEDULES[schedule]
    if phase != "marks":
        require(created.weekday() == 0, "Weekly clock did not originate on Monday")
    return phase


def fill_window(witnessed, now, wait):
    """Require a public state witness before the fixing; wait once for publication latency."""
    fixing = datetime.combine(witnessed.date(), time(0, 45), UTC)
    read_at = fixing + timedelta(seconds=75)
    delay = (read_at - witnessed).total_seconds()
    if witnessed.weekday() != 0 or witnessed >= fixing or delay > 390:
        return False
    wait(delay)
    return read_at <= now() <= fixing + timedelta(minutes=5)


def state_files(state, max_bytes):
    permitted = {"registration.json", "README.md", "status.json"}
    count = 0
    for child in state.iterdir():
        if child.name == ".git":
            continue
        require(not child.is_symlink(), "Symlink in evidence tree")
        if child.name == "events":
            require(child.is_dir(), "Expected an events directory")
            for event in child.iterdir():
                require(EVENT.fullmatch("events/" + event.name) and
                        not event.is_symlink() and event.is_file(), "Unexpected event path")
                count += event.stat().st_size
        else:
            require(child.name in permitted and child.is_file(), "Unexpected evidence path")
            count += child.stat().st_size
    require(count <= max_bytes, "Evidence size ceiling reached")


def publish(state, phase):
    entries = git(state, "status", "--porcelain=v1", "--untracked-files=all", "-z").split("\0")
    changed = []
    for entry in filter(None, entries):
        status, path = entry[:2], entry[3:]
        require((path == "status.json" and status in (" M", "??")) or
                (EVENT.fullmatch(path) and status == "??"), "Existing evidence or registration changed")
        changed.append(path)
    remote_witness(state)
    if changed:
        git(state, "add", "--", *changed)
        git(state, "-c", "user.name=github-actions[bot]", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-m", "Record scheduled allocation observation (" + phase + ")")
        git(state, "push", "origin", "HEAD:refs/heads/" + BRANCH)
    return remote_witness(state)


def metered_source(closes, quote, limit, closeout, now):
    # Signal acquisition uses two HTTP responses; a daily mark or minute quote uses one.
    def reserve(requests):
        nonlocal limit
        require(limit >= requests and now() < closeout, "Public source budget or horizon exhausted")
        limit -= requests

    def read_closes(cutoff, count=21):
        require(count in (1, 21), "Unexpected close count")
        reserve(2 if count == 21 else 1)
        return closes(cutoff, count=count)

    def read_quote(event):
        reserve(1)
        return quote(event)

    return read_closes, read_quote


def scheduled():
    from observations.prospective_source import capture_closes, capture_quote
    from observations.recorder import run, validate

    phase = phase_from_event(os.environ)
    code = Path(__file__).resolve().parents[1]
    state = Path(os.environ["GITHUB_WORKSPACE"]) / "record"
    protocol = registered(code, state, os.environ["REGISTRATION_SHA"])
    state_files(state, protocol["limits"]["max_state_bytes"])
    validate(state, protocol)
    revision = remote_witness(state)
    now = lambda: datetime.now(UTC)
    witnessed = now()
    phase_from_event(os.environ, witnessed)  # Recheck after checkout validation and remote witness.
    closeout = datetime.fromisoformat(protocol["closeout"])
    first, last = date.fromisoformat(protocol["start"]), date.fromisoformat(protocol["end"])
    if witnessed.date() < first or (phase != "marks" and witnessed.date() > last):
        return False
    options = {}
    if phase == "fill":
        if not fill_window(witnessed, now, sleep):
            print("No eligible pre-fixing witness or receipt window. The marks job reconciles misses.")
            return False
        options.update(witnessed_at=witnessed, witness_revision=revision)

    closes, quote = metered_source(capture_closes, capture_quote,
                                 protocol["limits"]["requests_per_job"], closeout, now)
    run(state, protocol, phase, now=now, closes=closes, quote=quote, **options)
    state_files(state, protocol["limits"]["max_state_bytes"])
    validate(state, protocol)
    confirmed = publish(state, phase)
    status = json.loads((state / "status.json").read_bytes())
    print(f"Confirmed observation record {confirmed}")
    return phase == "marks" and witnessed >= closeout and status.get("closed") is True


if __name__ == "__main__":
    closed = scheduled()
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write("closed=" + str(closed).lower() + "\n")
