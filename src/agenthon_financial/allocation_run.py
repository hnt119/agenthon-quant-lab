"""Replay the frozen, retrospective weekly BTC allocation and drawdown study."""
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import platform
from uuid import uuid4

import numpy as np

from agenthon_quant import __version__
from agenthon_quant.records import digest, strict_json, write_json
from agenthon_quant.resources import checkout_commit, resource_root
from .allocation_analysis import diagnostics, primary_comparison
from .allocation_books import allocation_entries
from .allocation_report import write_report
from .allocation_verify import verify_allocation, verify_interval
from .analysis import group
from .cost_books import _summaries
from .reproduce import SAVED, admitted_reference, compare
from .run import inputs, read_verified, sources, write_ledger
from .study import require
from .weekly_books import weekly_entries

STUDY = "btc-weekly-allocation-v1"
FREEZE = "cf2fa6ffc2a38f0b85cefa2545a53a65579507e7"
PROTOCOL = "46cbfbee2ef6aaa5e3bc5c184340c919d07babe97d0110fed2948157c3bb0f70"
ARTIFACTS = ("protocol.json", "ledger.jsonl.gz", "metrics.json", "comparisons.json",
             "verification.json", "README.md", "drawdown.svg", "public.json")


def calculate(out, spec, provenance):
    original = admitted_reference()
    record, parent, features, _, entries, _, _ = read_verified(SAVED)
    require(record == original and record["input_sha256"] == spec["snapshot_sha256"]
            and record["protocol_sha256"] == spec["source_protocol_sha256"]
            and record["source_manifest_sha256"] == spec["source_manifest_sha256"]
            and digest((SAVED / "run.json").read_bytes()) == spec["source_receipt_sha256"],
            "Allocation study parent identity mismatch")
    root = resource_root()
    weekly_ref = (root / "reports/btc-weekly-cadence-v1/metrics.json").read_bytes()
    weekly_protocol = (root / "experiments/btc-weekly-cadence-v1/protocol.json").read_bytes()
    require(digest(weekly_ref) == spec["weekly_metrics_sha256"] and
            digest(weekly_protocol) == spec["weekly_protocol_sha256"], "Weekly reference differs")
    prior_metrics = strict_json(weekly_ref)
    baseline = group(entries)
    _, rows = inputs()
    paths, summaries, checks, details = {}, {}, {}, {}
    for scenario, costs in spec["scenarios"].items():
        require(parent["scenarios"][scenario] == costs, "Parent cost assumption differs")
        weekly = weekly_entries(rows, features, parent, scenario)
        target, sizing = allocation_entries(rows, weekly, scenario, costs, spec["initial_cash"])
        arms = {"target50": target, "half_funded": sizing, "weekly20": weekly,
                "momentum20": baseline[scenario, "momentum20"], "passive_mix": baseline[scenario, "passive_mix"]}
        summaries[scenario] = _summaries((r for path in arms.values() for r in path), spec["initial_cash"])
        for arm in ("weekly20", "momentum20", "passive_mix"):
            require(compare(summaries[scenario][arm], prior_metrics[scenario][arm]),
                    f"Frozen {scenario} {arm} summaries differ")
        checks[scenario] = verify_allocation(rows, spec, scenario, arms, summaries[scenario])
        require(checks[scenario]["status"] == "passed", "Accounting verification failed")
        details[scenario] = diagnostics(arms, spec["initial_cash"])
        paths.update({(scenario, arm): path for arm, path in arms.items()})

    base = {arm: paths["base", arm] for arm in spec["arms"]}
    primary = primary_comparison(base, summaries["base"], spec)
    interval_check = verify_interval(base, spec, primary)
    write_ledger(out / "ledger.jsonl.gz", (r for path in paths.values() for r in path))
    write_json(out / "metrics.json", summaries)
    write_json(out / "comparisons.json", {"primary": primary, "diagnostics": details})
    write_json(out / "verification.json", {"status": "passed", "accounts": checks, "primary": interval_check,
               "frozen_comparators": "Three arms, three cost scenarios, pooled and all annual summaries matched."})
    write_report(out, spec, summaries, primary, details, paths, provenance)


def run(out=None):
    protocol = (resource_root() / "experiments" / STUDY / "protocol.json").read_bytes()
    require(digest(protocol) == PROTOCOL, "Allocation protocol differs from freeze")
    spec = strict_json(protocol)
    target = Path(out or Path.cwd() / "runs" / f"{STUDY}-{uuid4().hex[:12]}").expanduser().resolve()
    require(not target.exists(), f"Output already exists: {target}. Choose a fresh directory.")
    provenance = {k: spec[k] for k in ("snapshot_sha256", "source_receipt_sha256", "source_manifest_sha256",
                                        "weekly_protocol_sha256", "weekly_metrics_sha256")}
    provenance.update(protocol_commit=FREEZE, protocol_sha256=PROTOCOL)
    code = sources()
    for package, names in {
        "agenthon_financial": ("allocation_run", "allocation_analysis", "allocation_books", "allocation_report",
                              "allocation_verify", "weekly_books", "weekly_verify", "cost_books", "cost_verify",
                              "cost_report", "weekly_report", "compatibility", "reproduce"),
        "agenthon_quant": ("cli", "__init__"),
    }.items():
        for name in names:
            code[f"src/{package}/{name}.py"] = digest(files(package).joinpath(name + ".py").read_bytes())
    record = dict(study_id=STUDY, software_version=__version__, status="started", provenance=provenance,
                  code_files_sha256=code, checkout_commit=checkout_commit(), python=platform.python_version(),
                  numpy=np.__version__, started_utc=datetime.now(timezone.utc).isoformat(),
                  evidence="exploratory retrospective", prospective_observations=0, paid_usd=0, model_calls=0)
    target.mkdir(parents=True, exist_ok=False)
    write_json(target / "run.json", record)
    try:
        (target / "protocol.json").write_bytes(protocol)
        calculate(target, spec, provenance)
        record.update(status="passed", artifacts_sha256={p: digest((target/p).read_bytes()) for p in ARTIFACTS})
    except Exception as exc:
        record.update(status="failed", error=str(exc))
        raise
    finally:
        record["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(target / "run.json", record)
    print(f"Weekly BTC allocation verified.\nReport: {target/'README.md'}\nFigure: {target/'drawdown.svg'}\nReceipt: {target/'run.json'}")
    return 0
