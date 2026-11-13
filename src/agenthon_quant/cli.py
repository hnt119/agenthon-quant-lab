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
    diagnostics = sub.add_parser("doctor", help="Check local setup without model or data-provider calls")
    diagnostics.add_argument("--json", action="store_true", help="Machine-readable diagnostics")
    example = sub.add_parser("example", help="Run a bundled example from any working directory")
    example.add_argument("workflow", choices=("options", "trading"))
    example.add_argument("--out", type=Path, required=True)
    archive = sub.add_parser("archive", help="Search curated papers or historical experiment metadata")
    archive.add_argument("category", choices=("papers", "experiments"))
    archive.add_argument("query", nargs="?", default="")
    archive.add_argument("--status", help="Exact status (paper adaptation_status or experiment status), case-insensitive")
    archive.add_argument("--json", action="store_true", help="Return complete matching records")
    bundle = sub.add_parser("bundle", help="Create a private ZIP of verified run artifacts and input snapshots")
    bundle.add_argument("run_dir", type=Path)
    bundle.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            from .onboarding import doctor
            result = doctor()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Setup: {result['status']}")
                for check in result["checks"]:
                    print(f"[{check['status']}] {check['name']}: {check['details']}")
                print(result["next_step"])
            return 0 if result["status"] == "ready" else 2
        if args.command == "archive":
            from .archive import search_archive
            from .onboarding import repository_root
            matches = search_archive(repository_root(), args.category, args.query, args.status)
            if args.json:
                print(json.dumps({"category": args.category, "count": len(matches), "records": matches}, indent=2, ensure_ascii=False))
            else:
                print(f"{len(matches)} {args.category} match(es); local metadata only, no historical run executed.")
                for record in matches:
                    print(f"{record.get('id', 'unidentified')} | {record.get('title', 'Untitled')} | {record.get('adaptation_status' if args.category == 'papers' else 'status', 'unknown')}")
                    detail = record.get("summary") or record.get("finding") or record.get("hypothesis")
                    if isinstance(detail, str):
                        print(f"  {detail}")
            return 0
        if args.command == "bundle":
            from .onboarding import bundle_run
            print(json.dumps(bundle_run(args.run_dir, args.out), indent=2))
            return 0
        if args.command == "example":
            from .onboarding import example_path
            result = execute(example_path(args.workflow), args.out)
        elif args.command == "run":
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
        guidance = ""
        if "Source fingerprint differs" in str(error):
            guidance = " Use a separate checkout of the saved run's code.git_commit and recorded dependencies; keep the current checkout and original run intact. There is no bypass."
        parser.exit(2, f"quant-lab: {error}{guidance}\n")
