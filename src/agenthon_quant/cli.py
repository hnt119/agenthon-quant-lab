"""One command surface for human use, the skill and a future dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .records import execute, reproduce, strict_json, verify_saved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quant-lab")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Calculate and save a new inspectable run")
    run.add_argument("spec", type=Path)
    run.add_argument("--out", type=Path, required=True)
    replay = sub.add_parser("reproduce", help="Verify snapshots/code and rerun")
    replay.add_argument("run_dir", type=Path)
    replay.add_argument("--out", type=Path, required=True)
    replay.add_argument("--set", action="append", default=[], metavar="KEY=JSON", help="Record an intentional assumption change")
    explain = sub.add_parser("explain", help="Read saved validation results without calculating")
    explain.add_argument("run_dir", type=Path)
    verify = sub.add_parser("verify-inputs", help="Check saved snapshot and specification hashes")
    verify.add_argument("run_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            result = execute(args.spec, args.out)
        elif args.command == "reproduce":
            changes = {}
            for setting in args.set:
                key, separator, value = setting.partition("=")
                if not separator or not key or key in changes:
                    raise ValueError("Each --set must be a unique KEY=JSON value")
                changes[key] = strict_json(value)
            result = reproduce(args.run_dir, args.out, changes)
        elif args.command == "verify-inputs":
            verify_saved(args.run_dir)
            print("Input snapshots and effective specification match recorded hashes.")
            return 0
        else:
            result = strict_json((args.run_dir / "run.json").read_bytes())
            print(json.dumps({"status": result["status"], "error": result.get("error"), "checks": result["analysis"]["checks"], "warnings": result["analysis"]["warnings"]}, indent=2))
            return 0
        print(json.dumps({"status": result["status"], "checks": result["check_counts"], "report": str(args.out.resolve() / "report.md")}, indent=2))
        return 0 if result["status"] == "passed" else 2
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"quant-lab: {error}\n")
