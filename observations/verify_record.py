"""Read back the registered protocol, every public witness, and every paper-account transition."""
import argparse
import json
from pathlib import Path

from observations.recorder import Journal, canonical, validate
from observations.run_job import git, registered, require


def verify(record):
    registration = json.loads((record / "registration.json").read_bytes())
    code = Path(__file__).resolve().parents[1]
    protocol = registered(code, record, registration["revision"])
    report = validate(record, protocol)
    decisions = {}
    for index, event in enumerate(Journal(record, protocol).events, 1):
        if event["kind"] == "decision" and event["data"]["status"] == "accepted":
            decisions[event["day"]] = (f"events/{index:05d}.json", event)
        if event["kind"] == "fill" and event["data"]["status"] == "accepted":
            rev = event["data"]["witness_revision"]
            path, original = decisions[event["day"]]
            git(record, "merge-base", "--is-ancestor", rev, "HEAD")
            raw = git(record, "show", f"{rev}:{path}") + "\n"
            require(raw.encode() == canonical(original), "Witness lacks the recorded decision")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    print(json.dumps(verify(parser.parse_args().record), indent=2))
