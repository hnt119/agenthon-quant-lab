"""One command surface for human use, the skill and a future dashboard."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .records import execute, reproduce, strict_json, verify_saved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="quant-lab")
    from . import __version__
    parser.add_argument("--version", action="version", version=f"Quant Lab {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    btc = sub.add_parser("btc-study", help="Reproduce the frozen Bitstamp BTC research and open its results from the printed paths")
    btc.add_argument("--out", type=Path, help="New run folder. Defaults to a unique folder under ./runs")
    costs = sub.add_parser("btc-cost-break-even", help="Replay the frozen retrospective BTC cost grid and crossings")
    costs.add_argument("--out", type=Path, help="New output directory (defaults to a unique folder under ./runs)")
    weekly = sub.add_parser("btc-weekly-cadence", help="Replay Sunday-close BTC momentum against daily and passive accounts")
    weekly.add_argument("--out", type=Path, help="New output directory (defaults to a unique folder under ./runs)")
    allocation = sub.add_parser("btc-weekly-allocation", help="Compare a Monday 50% BTC target with a half-funded weekly account")
    allocation.add_argument("--out", type=Path, help="Fresh output directory for the frozen allocation study")
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
    example.add_argument("workflow", choices=("options", "trading", "historical"))
    example.add_argument("--out", type=Path, required=True)
    inspect = sub.add_parser("inspect-data", help="Inspect daily prices and quality using a local JSON input specification")
    inspect.add_argument("spec", type=Path)
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
        if args.command in ("btc-cost-break-even", "btc-weekly-cadence", "btc-weekly-allocation"):
            print(f"Quant Lab {__version__} · frozen study reproduction")
            print("The saved report retains its original build instructions. "
                  "Current installation and commands: https://github.com/hnt119/agenthon-quant-lab/blob/v0.5.0/docs/user-guide.md")
        if args.command == "btc-weekly-allocation":
            from agenthon_financial.allocation_run import run as replay_allocation
            return replay_allocation(args.out)
        if args.command == "btc-weekly-cadence":
            from agenthon_financial.weekly_run import run as run_weekly
            return run_weekly(args.out)
        if args.command == "btc-cost-break-even":
            from agenthon_financial.cost_run import run as run_cost_study
            return run_cost_study(args.out)
        if args.command == "btc-study":
            from agenthon_financial.reproduce import reproduce as reproduce_btc
            return reproduce_btc(args.out)
        if args.command == "inspect-data":
            from .historical import SPEC_KEYS
            from .market_data import read_market_data
            from .records import bounded_read, MAX_SPEC_BYTES
            spec = strict_json(bounded_read(args.spec, MAX_SPEC_BYTES))
            if not isinstance(spec, dict) or not isinstance(spec.get("data"), str) or not spec["data"].strip():
                raise ValueError("Specify a local data path in a JSON object")
            unsupported = set(spec) - SPEC_KEYS
            if unsupported:
                raise ValueError(f"Unknown specification fields: {', '.join(sorted(unsupported))}")
            if spec.get("workflow", "historical") != "historical":
                raise ValueError("inspect-data accepts a historical or data-only specification")
            _, quality = read_market_data(args.spec.resolve().parent / spec["data"], spec)
            print(json.dumps(quality, indent=2, ensure_ascii=False))
            return 0
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
            guidance = " Use the matching distribution or source checkout and the dependency versions recorded in run.json."
        parser.exit(2, f"quant-lab: {error}{guidance}\n")
