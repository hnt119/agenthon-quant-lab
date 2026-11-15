#!/usr/bin/env python3
"""Run offline release checks and preserve reports, including deliberate failures."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agenthon_quant.options import run as options, verify as verify_options
from agenthon_quant.records import code_identity, digest, strict_json, verify_saved, write_json
from agenthon_quant.trading import load_prices, run as trading, verify_ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="A new directory")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    started = time.monotonic()
    test_command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    tests = subprocess.run(test_command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    (out / "tests.log").write_text(tests.stdout + tests.stderr)
    commands = []
    helper = ROOT / "skills/quant-research/scripts/quant.py"
    cases = [
        ("options", ["run", str(ROOT / "examples/options.json")], 0),
        ("trading", ["run", str(ROOT / "examples/trading.json")], 0),
        ("historical", ["example", "historical"], 0),
        ("historical-reproduced", ["reproduce", str(out / "historical")], 0),
        ("invalid-options", ["run", str(ROOT / "examples/invalid-options.json")], 2),
        ("options-reproduced", ["reproduce", str(out / "options")], 0),
        ("options-vol30", ["reproduce", str(out / "options"), "--set", "volatility=0.3"], 0),
    ]
    successful = tests.returncode == 0
    for name, arguments, expected in cases:
        command = [sys.executable, str(helper), *arguments, "--out", str(out / name)]
        process = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        (out / f"{name}.log").write_text(process.stdout + process.stderr)
        record_path = out / name / "run.json"
        record = strict_json(record_path.read_bytes()) if record_path.exists() else {}
        passed = process.returncode == expected and record.get("status") == ("invalid" if expected else "passed")
        successful &= passed
        commands.append({"case": name, "command": command, "expected_exit": expected, "exit": process.returncode,
                         "verified": passed, "run_record_sha256": digest(record_path.read_bytes()) if record_path.exists() else None,
                         "check_counts": record.get("check_counts")})
    explanation_command = [sys.executable, str(helper), "explain", str(out / "invalid-options")]
    explanation = subprocess.run(explanation_command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    (out / "explain-invalid.log").write_text(explanation.stdout + explanation.stderr)
    successful &= explanation.returncode == 0 and "volatility" in explanation.stdout
    option_record = verify_saved(out / "options")
    repeated = verify_saved(out / "options-reproduced")
    same = option_record["analysis"] == repeated["analysis"]
    historical_record = verify_saved(out / "historical")
    repeated_history = verify_saved(out / "historical-reproduced")
    same_history = historical_record["analysis"] == repeated_history["analysis"]
    successful &= same and same_history
    spec = strict_json((ROOT / "examples/options.json").read_bytes())
    tampered = copy.deepcopy(options(spec)["results"])
    for side in ("call", "put"):
        tampered["valuations"][side]["price"] += 1
    checks = verify_options(spec, tampered)
    offset_detected = any(c["status"] == "failed" and "quadrature" in c["name"] for c in checks)
    parity_passed = next(c["status"] == "passed" for c in checks if c["name"] == "put_call_parity")
    trade_spec = strict_json((ROOT / "examples/trading.json").read_bytes())
    data = ROOT / "examples" / trade_spec["data"]
    result = trading(trade_spec, data)
    ledger = copy.deepcopy(result["results"]["strategy"]["net"]["ledger"])
    ledger[30]["cash"] += 100
    ledger_checks = verify_ledger(ledger, load_prices(data), trade_spec["initial_cash"], trade_spec["fee_bps"],
                                  trade_spec["slippage_bps"], trade_spec["lookback"])
    cash_detected = any(c["status"] == "failed" for c in ledger_checks)
    successful &= offset_detected and parity_passed and cash_detected
    write_json(out / "deliberate-failures.json", {
        "price_offset": {"hypothesis": "Parity alone can miss a shared price error", "mutation": "+1 to both base option prices",
                         "parity_still_passed": parity_passed, "independent_check_detected": offset_detected, "checks": checks},
        "ledger_cash": {"mutation": "+100 to row 31 closing cash", "detected": cash_detected, "checks": ledger_checks}})
    count = re.search(r"Ran (\d+) tests", tests.stderr)
    record = {"status": "passed" if successful else "failed", "code": code_identity(), "test_command": test_command,
              "test_exit": tests.returncode, "tests_run": int(count.group(1)) if count else None,
              "workflows": commands, "explain_invalid_exit": explanation.returncode,
              "exact_analysis_reproduced": same, "exact_historical_analysis_reproduced": same_history, "deliberate_price_error_detected": offset_detected,
              "deliberate_cash_error_detected": cash_detected, "model_calls": 0, "paid_services_cost_usd": 0,
              "elapsed_seconds": time.monotonic() - started}
    write_json(out / "verification.json", record)
    print(json.dumps({"status": record["status"], "tests": record["tests_run"], "evidence": str(out / "verification.json")}, indent=2))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
