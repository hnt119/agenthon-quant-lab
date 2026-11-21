"""Version-pinned run, snapshot replay and read-only verification."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from agenthon_quant.market_data import read_market_data
from agenthon_quant.records import bounded_read, code_identity, digest, strict_json, verify_saved, write_json

from .pilot import ARMS, calculate
from .verify import verify

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "experiments/btc-momentum-pilot"
PROTOCOL = "607c365cf4266cf2e3fb056de7dff861251ca1a7579e2fde8a3505d55587a2ac"
FREEZE = "d9f9f92ef9777a937502ba6ac1b0cf07a805fd4c"
OUTPUTS = ("features.jsonl", "ledger.jsonl", "fit.json", "metrics.json", "verification.json")
LIMIT = 16 * 1024 * 1024


def source_code():
    code = code_identity()
    code.pop("source_root")
    paths = [*Path(__file__).parent.glob("*.py"), ROOT / "scripts/btc_pilot.py", ROOT / "scripts/edge_lab_spectral.py"]
    code["pilot_files_sha256"] = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}
    return code


def fixed_inputs(protocol, prices, provenance):
    if digest(protocol) != PROTOCOL:
        raise ValueError("Expected the frozen BTC pilot protocol")
    spec = strict_json(protocol)
    if (digest(prices), digest(provenance)) != (spec["data_sha256"], spec["source_manifest_sha256"]):
        raise ValueError("Daily data or source manifest differs from the freeze")
    return spec, strict_json(provenance)


def prices_at(path, source):
    rows, quality = read_market_data(path, {
        "source": source["attribution"], "price_adjustment": "unadjusted", "timestamp_convention": "session_date",
        "columns": {"date": "SessionUTC", "open": "FirstTradeOpen", "close": "LastTradeClose"}})
    q = source["quality"]
    if (quality["input_sha256"] != q["daily_sha256"] or len(rows) != q["sessions"]
            or quality["calendar_gaps"]["unobserved_calendar_days"] or rows[0]["date"] != q["first_session"]
            or rows[-1]["date"] != q["last_session"]):
        raise ValueError("Daily market-data qualification failed")
    return rows, quality


def write_lines(path, items):
    with path.open("x", encoding="utf8") as handle:
        for item in items:
            handle.write(json.dumps(item, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def read_lines(path):
    return [strict_json(line) for line in bounded_read(path, LIMIT).splitlines()]


def execute(out, protocol, prices, provenance):
    spec, source = fixed_inputs(protocol, prices, provenance)
    out.mkdir(parents=True, exist_ok=False)
    folder = out / "inputs"
    folder.mkdir()
    (out / "spec.json").write_bytes(protocol)
    (folder / "data.csv").write_bytes(prices)
    (folder / "source.json").write_bytes(provenance)
    record = {"workflow": "btc_research_pilot", "protocol_commit": FREEZE, "status": "started",
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "code": source_code(),
              "effective_specification_sha256": PROTOCOL, "specification": spec, "model_calls": 0, "paid_cost_usd": 0,
              "input_provenance": [{"snapshot": "inputs/data.csv", "sha256": digest(prices)},
                                  {"snapshot": "inputs/source.json", "sha256": digest(provenance)}]}
    try:
        rows, quality = prices_at(folder / "data.csv", source)
        result = calculate(rows, quality, spec)
        write_lines(out / "features.jsonl", result["signals"])
        write_lines(out / "ledger.jsonl", ({"arm": arm, "treatment": t, **r} for arm in ARMS for t in ("gross", "net")
                                        for r in result["books"][arm][t]))
        write_json(out / "metrics.json", result["metrics"])
        write_json(out / "fit.json", result["fit"])
        write_json(out / "verification.json", result["checks"])
        record["check_counts"] = dict(Counter(c["status"] for c in result["checks"]))
        record["status"] = "passed" if all(c["status"] == "passed" for c in result["checks"]) else "failed"
        record["output_artifacts_sha256"] = {f: digest((out / f).read_bytes()) for f in OUTPUTS}
    except Exception as exc:
        record.update(status="failed", error=str(exc))
        raise
    finally:
        write_json(out / "run.json", record)
    if record["status"] != "passed":
        raise ValueError("Pilot verification failed. See the preserved verification.json")
    return record


def run(out):
    return execute(out, *((EXPERIMENT / f).read_bytes() for f in ("protocol.json", "daily.csv", "source.json")))


def saved(folder):
    """Authenticate fixed names and source identities before consuming saved observations."""
    rec = strict_json(bounded_read(folder / "run.json", LIMIT))
    if (rec["workflow"] != "btc_research_pilot" or rec["status"] != "passed"
            or rec["protocol_commit"] != FREEZE or rec["effective_specification_sha256"] != PROTOCOL
            or [v["snapshot"] for v in rec["input_provenance"]] != ["inputs/data.csv", "inputs/source.json"]
            or set(rec["output_artifacts_sha256"]) != set(OUTPUTS)):
        raise ValueError("Expected a completed frozen BTC pilot")
    verify_saved(folder)
    spec, source = fixed_inputs(*[bounded_read(folder / f, LIMIT) for f in ("spec.json", "inputs/data.csv", "inputs/source.json")])
    if rec["specification"] != spec:
        raise ValueError("Saved specification mismatch")
    code = source_code()
    for key in ("source_fingerprint_sha256", "pilot_files_sha256", "dependencies", "python"):
        if rec["code"][key] != code[key]:
            raise ValueError(f"Use the recorded code and environment ({key})")
    for f, h in rec["output_artifacts_sha256"].items():
        if digest(bounded_read(folder / f, LIMIT)) != h:
            raise ValueError(f"Artifact digest mismatch: {f}")
    return rec, spec, source


def load_results(folder):
    features = read_lines(folder / "features.jsonl")
    books = {a: {t: [] for t in ("gross", "net")} for a in ARMS}
    for row in read_lines(folder / "ledger.jsonl"):
        arm, t = row.pop("arm"), row.pop("treatment")
        books[arm][t].append(row)
    return features, strict_json((folder / "fit.json").read_bytes()), books, strict_json((folder / "metrics.json").read_bytes())


def audit(folder):
    rec, spec, source = saved(folder)
    rows, _ = prices_at(folder / "inputs/data.csv", source)
    checks = verify(rows, spec, *load_results(folder))
    original = strict_json((folder / "verification.json").read_bytes())
    if (not all(c["status"] == "passed" for c in checks) or original[-len(checks):] != checks
            or not all(c["status"] == "passed" for c in original)
            or dict(Counter(c["status"] for c in original)) != rec["check_counts"]):
        raise ValueError("Independent readback disagrees with the saved receipts")
    return {"status": "passed", "independent_checks": len(checks), "recorded_checks": len(original)}


def replay(folder, out):
    audit(folder)
    reference = strict_json((folder / "run.json").read_bytes())
    rec = execute(out, *((folder / f).read_bytes() for f in ("spec.json", "inputs/data.csv", "inputs/source.json")))
    if rec["output_artifacts_sha256"] != reference["output_artifacts_sha256"]:
        rec.update(status="failed", error="Replay differs from the recorded result")
        write_json(out / "run.json", rec)
        raise ValueError(rec["error"])
    return rec
