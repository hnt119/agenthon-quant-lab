"""Inspectable runs; inputs are snapshotted before any calculation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__

MAX_SPEC_BYTES = 1_048_576
MAX_DATA_BYTES = 25 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(data: bytes | str) -> Any:
    def invalid(value):
        raise ValueError(f"Non-finite JSON literal: {value}")
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=invalid)


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def bounded_read(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"Input exceeds {limit} byte limit")
    return data


def code_identity() -> dict:
    package = Path(__file__).resolve().parent
    root = package.parent.parent
    paths = sorted(package.rglob("*.py"))
    if (root / "pyproject.toml").exists():
        paths.append(root / "pyproject.toml")
    files = {str(p.relative_to(root)): digest(p.read_bytes()) for p in paths}
    fingerprint = digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    commit = None
    dirty = None
    # An installed wheel must not acquire an unrelated ancestor repository identity.
    if (root / ".git").exists():
        try:
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
            status = subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--", "src", "pyproject.toml"], text=True)
            dirty = bool(status.strip())
        except (OSError, subprocess.CalledProcessError):
            pass
    versions = {}
    for dependency in ("scipy", "numpy", "pyarrow"):
        try:
            versions[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            versions[dependency] = None
    return {"package_version": __version__, "git_commit": commit,
            "runtime_source_dirty": dirty, "source_root": str(root),
            "source_fingerprint_sha256": fingerprint, "files_sha256": files,
            "python": platform.python_version(), "dependencies": versions}


def _command(path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        shown = path.relative_to(root)
    except ValueError:
        shown = path
    return f"python -m agenthon_quant reproduce {shlex.quote(str(shown))} --out runs/reproduced-NEW"


def _summary(value: Any) -> Any:
    """Keep reports readable while the run JSON retains full ledgers."""
    if isinstance(value, dict):
        return {k: _summary(v) for k, v in value.items() if k not in {"ledger", "daily", "trades", "decisions", "rows"}}
    if isinstance(value, list) and len(value) > 15:
        return {"rows": len(value), "preview": value[:3], "full_data": "run.json"}
    return value


def _results_markdown(workflow: str, result: dict) -> list[str]:
    def number(value):
        return "unavailable" if value is None else f"{value:.8g}"
    if workflow == "options" and "valuations" in result:
        lines = ["Prices are per unit of underlying; derivative units are specified below.", "",
                 "| Option | Price | Delta | Gamma | Vega | Rho | Theta/year |",
                 "|---|---:|---:|---:|---:|---:|---:|"]
        for side, values in result["valuations"].items():
            quantities = [values["price"], *(values["greeks"][g] for g in ("delta", "gamma", "vega", "rho", "theta"))]
            lines.append("| " + side + " | " + " | ".join(number(x) for x in quantities) + " |")
        if result.get("volatility_scenarios"):
            lines += ["", "### Volatility scenarios", "", "| Annual volatility | Option | Price |", "|---:|---|---:|"]
            for scenario in result["volatility_scenarios"]:
                for side, values in scenario["valuations"].items():
                    lines.append(f"| {scenario['volatility']:.2%} | {side} | {number(values['price'])} |")
        return lines
    if workflow == "trading" and "strategy" in result:
        lines = ["Returns include the initial warmup in cash. Both portfolios begin trading after the same warmup; final positions are marked without liquidation.", "",
                 "| Portfolio | Costs | Return | Max drawdown | Mean exposure | Turnover | Fees | Slippage | Final equity | Trades |",
                 "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name in ("strategy", "buy_and_hold"):
            for cost in ("gross", "net"):
                m = result[name][cost]["metrics"]
                lines.append(f"| {name} | {cost} | {m['total_return']:.4%} | {m['max_drawdown']:.4%} | {m['mean_close_exposure']:.2%} | {m['turnover']:.4f} | {m['fees']:.4f} | {m['slippage_cost']:.4f} | {m['ending_equity']:.4f} | {m['trade_events']} |")
        lines += ["", "### Chronological periods", "", "| Portfolio | Costs | Period | Start | End | Return | Drawdown |", "|---|---|---|---|---|---:|---:|"]
        for name in ("strategy", "buy_and_hold"):
            for cost in ("gross", "net"):
                for period, m in result[name][cost]["periods"].items():
                    lines.append(f"| {name} | {cost} | {period} | {m['start']} | {m['end']} | {m['total_return']:.4%} | {m['max_drawdown']:.4%} |")
        lines += ["", "Full position, cash, trade, cost and P&L ledgers are retained in `run.json`."]
        return lines
    return ["```json", json.dumps(_summary(result), indent=2, allow_nan=False), "```"]


def render_report(record: dict) -> str:
    outcome = record.get("analysis", {})
    checks = outcome.get("checks", [])
    lines = [f"# Agenthon Quant Lab — {record.get('workflow', 'invalid request')}", "",
             f"**Status: {record['status']}** · v{__version__} · {record['started_at_utc']}", "",
             "This is an offline calculation/simulation. Numerical checks do not establish predictive accuracy or trading profitability.", "",
             "## Results", "", *_results_markdown(record.get("workflow"), outcome.get("results", {})), "",
             "## Specification", "", "```json", json.dumps(record.get("specification", {}), indent=2, allow_nan=False), "```", "",
             "## Assumptions", "", "```json", json.dumps(outcome.get("assumptions", {}), indent=2, allow_nan=False), "```", "",
             "## Verification", "", "| Check | Status | Evidence |", "|---|---|---|"]
    for check in checks:
        detail = str(check.get("details", check.get("message", ""))).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check['name']} | {check['status']} | {detail} |")
    lines += ["", "## Warnings and limitations", ""]
    for warning in outcome.get("warnings", []):
        lines.append(f"- {warning}")
    if record.get("error"):
        lines.append(f"- {record['error']}")
    if not outcome.get("warnings") and not record.get("error"):
        lines.append("- Only the workflow and conventions specified above were tested.")
    lines += ["", "## Provenance and reproduction", "",
              f"Source commit: `{record['code']['git_commit']}`; runtime source dirty: `{record['code']['runtime_source_dirty']}`.", "",
              f"Source fingerprint (SHA-256, distinct from Git): `{record['code']['source_fingerprint_sha256']}`.", "",
              f"Elapsed seconds: {record['elapsed_seconds']:.6f}. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.", "",
              "Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).", "",
              "From the repository root, using the documented environment:", "", "```sh", record["reproduce_command"], "```", ""]
    return "\n".join(lines)


def execute(spec_path: Path, out: Path, *, derived_from: dict | None = None) -> dict:
    """Never overwrite a run. Validation failures still get a record and report."""
    started = time.monotonic()
    spec_path, out = spec_path.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = out / "inputs"
    inputs.mkdir()
    record = {"schema_version": 1, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "invalid", "workflow": None, "code": code_identity(),
              "input_provenance": [], "model_usage": {"mode": "disabled", "calls": 0, "tokens": 0, "cost_usd": 0},
              "random_seed": None, "reproduce_command": _command(out)}
    if derived_from is not None:
        record["derived_from"] = derived_from
    try:
        raw = bounded_read(spec_path, MAX_SPEC_BYTES)
        (inputs / "request.json").write_bytes(raw)
        record["input_provenance"].append({"role": "request", "original_path": str(spec_path), "snapshot": "inputs/request.json", "sha256": digest(raw), "bytes": len(raw)})
        spec = strict_json(raw)
        if not isinstance(spec, dict):
            raise ValueError("Specification must be a JSON object")
        # Re-serialization rejects overflowed JSON numbers, including 1e999.
        json.dumps(spec, allow_nan=False)
        record["specification"] = spec
        record["workflow"] = spec.get("workflow")
        effective = dict(spec)
        if spec.get("workflow") == "trading":
            if not isinstance(spec.get("data"), str) or not spec["data"]:
                raise ValueError("Trading specification needs a data path")
            source = (spec_path.parent / spec["data"]).resolve()
            if source.suffix.lower() not in {".csv", ".parquet"}:
                raise ValueError("Data must be CSV or Parquet")
            data = bounded_read(source, MAX_DATA_BYTES)
            snapshot = inputs / ("data" + source.suffix.lower())
            snapshot.write_bytes(data)
            snapshot.chmod(0o444)
            record["input_provenance"].append({"role": "market_data", "original_path": str(source), "snapshot": str(snapshot.relative_to(out)), "sha256": digest(data), "bytes": len(data)})
            effective["data"] = str(snapshot.relative_to(out))
        write_json(out / "spec.json", effective)
        record["effective_specification_sha256"] = digest((out / "spec.json").read_bytes())
        if spec.get("workflow") == "options":
            from .options import run
            analysis = run(spec)
        elif spec.get("workflow") == "trading":
            from .trading import run
            analysis = run(spec, snapshot)
        else:
            raise ValueError("Supported workflows are options and trading")
        record["analysis"] = analysis
        checks = analysis.get("checks", [])
        if not checks or any(c.get("status") not in {"passed", "failed", "unavailable"} for c in checks):
            raise ValueError("Workflow returned invalid or empty verification")
        record["check_counts"] = {state: sum(c["status"] == state for c in checks) for state in ("passed", "failed", "unavailable")}
        record["status"] = "failed" if record["check_counts"]["failed"] else "passed"
        # Serialization itself is an output contract check, before publishing.
        json.dumps(record, allow_nan=False)
    except (ValueError, TypeError, KeyError, OSError, ArithmeticError, ImportError) as error:
        record["status"] = "invalid"
        record["error"] = str(error)
        record["analysis"] = {"results": {}, "assumptions": {}, "warnings": [],
                              "checks": [{"name": "input_and_execution_contract", "status": "failed", "details": str(error)}]}
        record["check_counts"] = {"passed": 0, "failed": 1, "unavailable": 0}
        # Invalid specification values remain in the byte-exact request snapshot.
        try:
            json.dumps(record.get("specification"), allow_nan=False)
        except ValueError:
            record.pop("specification", None)
    record["elapsed_seconds"] = time.monotonic() - started
    try:
        if record["status"] == "passed":
            write_json(out / "validated-results.json", record["analysis"]["results"])
        (out / "report.md").write_text(render_report(record))
        # The completed run record is the commit marker, written last.
        write_json(out / "run.json", record)
    except OSError as error:
        record["status"] = "failed"
        record["error"] = f"Artifact publication failed: {error}"
        record["analysis"]["checks"].append({"name": "artifact_publication", "status": "failed", "details": str(error)})
        record["check_counts"]["failed"] += 1
        (out / "validated-results.json").unlink(missing_ok=True)
        (out / "report.md").write_text(render_report(record))
        write_json(out / "run.json", record)
    return record


def verify_saved(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    record = strict_json((run_dir / "run.json").read_bytes())
    for item in record["input_provenance"]:
        path = (run_dir / item["snapshot"]).resolve()
        if not path.is_relative_to(run_dir):
            raise ValueError("Snapshot path escapes run directory")
        if digest(bounded_read(path, MAX_DATA_BYTES)) != item["sha256"]:
            raise ValueError(f"Input snapshot hash mismatch: {item['snapshot']}")
    spec_path = run_dir / "spec.json"
    if not record.get("effective_specification_sha256") or digest(spec_path.read_bytes()) != record["effective_specification_sha256"]:
        raise ValueError("Effective specification missing or changed")
    return record


def reproduce(run_dir: Path, out: Path, overrides: dict | None = None) -> dict:
    """Verify frozen inputs/code, then rerun or record a deliberate assumption change."""
    import tempfile
    record = verify_saved(run_dir)
    if record["code"]["source_fingerprint_sha256"] != code_identity()["source_fingerprint_sha256"]:
        raise ValueError("Source fingerprint differs; use the recorded source version")
    original = (run_dir / "spec.json").resolve()
    if not overrides:
        return execute(original, out)
    spec = strict_json(original.read_bytes())
    spec.update(overrides)
    if spec.get("workflow") == "trading":
        spec["data"] = str((original.parent / spec["data"]).resolve())
    with tempfile.TemporaryDirectory(prefix="quant-assumptions-") as temporary:
        temporary_spec = Path(temporary) / "spec.json"
        write_json(temporary_spec, spec)
        result = execute(temporary_spec, out, derived_from={
            "run_record_sha256": digest((run_dir / "run.json").read_bytes()), "changes": overrides})
    return result
