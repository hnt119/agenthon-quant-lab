"""Reproduce the single prespecified BTC weekly cadence comparison offline."""
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import platform
from uuid import uuid4

from agenthon_quant import __version__
from agenthon_quant.records import digest, strict_json, write_json
from agenthon_quant.resources import checkout_commit, resource_root
from .analysis import group, intervals
from .cost_books import _summaries
from .reproduce import SAVED, admitted_reference, compare
from .run import inputs, read_verified, sources, write_ledger
from .study import books, require
from .weekly_books import weekly_entries
from .weekly_report import write_report
from .weekly_verify import verify_weekly


STUDY = "btc-weekly-cadence-v1"
FREEZE = "997f4f7d7f0ea2932a3f9caa3d8233c3983ccfc4"
PROTOCOL = "e73695d858486f71f5bc2c0aa8ade15b5e380ed197f5c5f7ef9509fea4afa425"
COMPARATORS = {"vs_passive": "passive_mix", "vs_daily": "momentum20"}
ARTIFACTS = ("protocol.json", "ledger.jsonl.gz", "metrics.json", "comparisons.json",
             "verification.json", "README.md", "weekly-cadence.svg", "public.json")


def comparisons(ledgers, metrics, spec, predictions):
    contrasts = {}
    for scenario, arms in metrics.items():
        contrasts[scenario] = {}
        for period, weekly in arms["weekly20"].items():
            result = {}
            for key, arm in COMPARATORS.items():
                a, b = weekly["sharpe"], arms[arm][period]["sharpe"]
                result[key] = a - b if None not in (a, b) else None
            contrasts[scenario][period] = result

    base = ledgers["base", "weekly20"]
    ci = {}
    for key, arm in COMPARATORS.items():
        baseline = ledgers["base", arm]
        require([r["date"] for r in base] == [r["date"] for r in baseline], "Misaligned paired dates")
        # Reuse the original paired-bootstrap RNG stream, including its label draws.
        # Only the Sharpe contrast is a declared endpoint in this study.
        ci[key] = intervals((base, baseline), predictions, spec["evaluation_years"], spec["uncertainty"])["sharpe_delta"]
    states = {(True, True): "both_long", (False, False): "both_cash",
              (True, False): "weekly_only", (False, True): "daily_only"}
    counts = dict.fromkeys(states.values(), 0)
    for weekly, daily in zip(base, ledgers["base", "momentum20"], strict=True):
        counts[states[weekly["shares"] > 0, daily["shares"] > 0]] += 1
    opportunities = [r["date"] for r in base if r["decision_time"] is not None]
    return dict(contrasts=contrasts, interval95=ci, position_days=counts,
                scheduled_opportunities=len(opportunities), first_opportunity=opportunities[0],
                first_fill=next((r["date"] for r in base if r["trade_quantity"]), None))


def calculate(out, spec, provenance):
    reference = admitted_reference()
    record, parent, features, fit, original, original_metrics, parent_check = read_verified(SAVED)
    require(record == reference and record["input_sha256"] == spec["snapshot_sha256"]
            and record["protocol_sha256"] == spec["source_protocol_sha256"]
            and record["source_manifest_sha256"] == spec["source_manifest_sha256"],
            "Weekly study parent identity mismatch")
    _, rows = inputs()
    original_paths = group(original)
    weights = {int(year): value for year, value in fit["annual_weights"].items()}
    controls = [arm for arm in spec["arms"] if arm != "weekly20"]
    require(all(parent["scenarios"][k] == v for k, v in spec["scenarios"].items())
            and parent["initial_cash"] == spec["initial_cash"]
            and parent["evaluation_years"] == spec["evaluation_years"], "Parent comparison definitions differ")
    control_spec = dict(parent, arms=controls, scenarios=spec["scenarios"])
    rebuilt = group(books(rows, features, weights, control_spec))
    entries, metrics, checks, compatibility = [], {}, {}, {}
    for scenario in spec["scenarios"]:
        weekly = weekly_entries(rows, features, parent, scenario)
        selection = list(weekly)
        for arm in controls:
            selection.extend(rebuilt[scenario, arm])
        metrics[scenario] = _summaries(selection, spec["initial_cash"])
        compatibility[scenario] = {}
        for arm in controls:
            path = rebuilt[scenario, arm]
            require(compare(path, original_paths[scenario, arm]) and
                    compare(metrics[scenario][arm], original_metrics["portfolios"][scenario][arm]),
                    f"Frozen baseline differs: {scenario} {arm}")
            compatibility[scenario][arm] = dict(matched_daily_rows=len(path), matched_periods=len(metrics[scenario][arm]))
        checks[scenario] = verify_weekly(rows, parent, scenario, weekly, metrics[scenario]["weekly20"])
        require(checks[scenario]["status"] == "passed", "Weekly accounting verification failed")
        entries.extend(selection)
    pred = strict_json((SAVED / "predictions.json").read_bytes())["5"]
    result = comparisons(group(entries), metrics, spec, pred)
    write_ledger(out / "ledger.jsonl.gz", entries)
    write_json(out / "metrics.json", metrics)
    write_json(out / "comparisons.json", result)
    write_json(out / "verification.json", dict(status="passed", parent=parent_check,
               weekly=checks, original_baselines=compatibility,
               baseline_comparison="Full daily records and period metrics meet original reproduction tolerances."))
    write_report(out, spec, metrics, result, provenance)


def run(out=None):
    raw = (resource_root() / "experiments" / STUDY / "protocol.json").read_bytes()
    require(digest(raw) == PROTOCOL, "Weekly protocol differs from the frozen specification")
    spec = strict_json(raw)
    require(digest((SAVED / "run.json").read_bytes()) == spec["source_receipt_sha256"], "Parent receipt differs")
    target = Path(out or Path.cwd() / "runs" / f"{STUDY}-{uuid4().hex[:12]}").expanduser().resolve()
    require(not target.exists(), f"Output already exists: {target}. Choose a new directory.")
    target.mkdir(parents=True, exist_ok=False)
    provenance = {k: spec[k] for k in ("snapshot_sha256", "source_receipt_sha256", "source_manifest_sha256")}
    provenance.update(protocol_commit=FREEZE, protocol_sha256=PROTOCOL)
    code = sources()
    for pkg, modules in {
        "agenthon_financial": ("weekly_run", "weekly_books", "weekly_report", "weekly_verify", "cost_books",
                               "cost_verify", "compatibility", "reproduce"),
        "agenthon_quant": ("cli", "__init__"),
    }.items():
        for name in modules:
            filename = name + ".py"
            code[f"src/{pkg}/{filename}"] = digest(files(pkg).joinpath(filename).read_bytes())
    receipt = dict(study_id=STUDY, status="started", provenance=provenance, code_files_sha256=code,
                   software_version=__version__, python=platform.python_version(), checkout_commit=checkout_commit(),
                   evidence="exploratory retrospective", started_utc=datetime.now(timezone.utc).isoformat(),
                   prospective_observations=0, model_calls=0, paid_usd=0)
    write_json(target / "run.json", receipt)
    try:
        (target / "protocol.json").write_bytes(raw)
        calculate(target, spec, provenance)
        receipt.update(status="passed", artifacts_sha256={n: digest((target/n).read_bytes()) for n in ARTIFACTS})
    except Exception as exc:
        receipt.update(status="failed", error=str(exc))
        raise
    finally:
        receipt["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(target / "run.json", receipt)
    print(f"Weekly BTC study verified.\nReport: {target/'README.md'}\nFigure: {target/'weekly-cadence.svg'}\nReceipt: {target/'run.json'}")
    return 0
