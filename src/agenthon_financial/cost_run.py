"""Run one frozen, descriptive transaction-cost sensitivity from bundled inputs."""
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
import platform
from uuid import uuid4

from agenthon_quant import __version__
from agenthon_quant.records import digest, strict_json, write_json
from agenthon_quant.resources import checkout_commit, resource_root
from .cost_books import CostBooks
from .cost_crossings import RefinementBudgetReached, crossings
from .cost_report import write_report
from .run import sources
from .study import require


STUDY = "btc-cost-break-even-v1"
PROTOCOL_COMMIT = "78f7486cbee975600b9d7f581533595f507a64f6"
PROTOCOL_SHA = "02ace6a5531f2a0debd68a929a82e63137b6e04d5ee6e42b45e0ad9b78b3d3b3"


def inventory():
    result = sources()
    modules = {
        "agenthon_financial": ["cost_run", "cost_books", "cost_verify", "cost_crossings", "cost_report",
                               "compatibility", "reproduce"],
        "agenthon_quant": ["cli", "__init__"],
    }
    for package, names in modules.items():
        for name in names:
            filename = name + ".py"
            result[f"src/{package}/{filename}"] = digest(files(package).joinpath(filename).read_bytes())
    return result


def run(out=None):
    raw = (resource_root() / "experiments" / STUDY / "protocol.json").read_bytes()
    require(digest(raw) == PROTOCOL_SHA, "The cost study protocol differs from the frozen revision")
    protocol = strict_json(raw)
    target = Path(out) if out else Path.cwd() / "runs" / f"{STUDY}-{uuid4().hex[:12]}"
    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=False)
    provenance = dict(protocol_commit=PROTOCOL_COMMIT, protocol_sha256=PROTOCOL_SHA,
                      snapshot_sha256=protocol["input_sha256"], original_receipt_sha256=protocol["source_receipt_sha256"],
                      code_files_sha256=inventory())
    receipt = dict(study_id=STUDY, software_version=__version__, python=platform.python_version(),
                   started_utc=datetime.now(timezone.utc).isoformat(), checkout_commit=checkout_commit(),
                   status="started", provenance=provenance, model_calls=0, paid_usd=0,
                   evidence="descriptive retrospective", prospective_observations=0)
    write_json(target / "run.json", receipt)
    try:
        (target / "protocol.json").write_bytes(raw)
        books = CostBooks()
        require(books.spec["snapshot_sha256"] == provenance["snapshot_sha256"] and
                books.verification["original_receipt_sha256"] == provenance["original_receipt_sha256"],
                "Source study identity differs")
        provenance["source_manifest_sha256"] = books.spec["source_manifest_sha256"]
        path, settings = protocol["cost_path"], protocol["search"]
        grid = [books.evaluate(i / path["grid_denominator"]) for i in range(path["grid_count"])]
        write_json(target / "grid.json", grid)
        cache = {row["lambda"]: row for row in grid}
        extra = []
        def evaluate(multiplier):
            if multiplier not in cache:
                if len(extra) >= settings["max_additional_settings"]:
                    raise RefinementBudgetReached()
                sample = books.evaluate(multiplier)
                cache[multiplier] = sample
                extra.append(sample)
            return cache[multiplier]

        records = {}
        for criterion in settings["criteria_order"]:
            samples = [(row["lambda"], row["differences"][criterion]) for row in grid]
            tolerance = settings["sharpe_zero_tolerance"] if criterion.endswith("_sharpe") else settings["wealth_zero_tolerance_usd"]
            records[criterion] = crossings(samples, lambda x: evaluate(x)["differences"][criterion],
                                           zero_tolerance=tolerance,
                                           width_tolerance=settings["lambda_width_tolerance"],
                                           max_midpoints=settings["max_midpoints_per_bracket"])
        write_json(target / "refinements.json", extra)
        write_json(target / "crossings.json", records)
        require(books.verification["settings_checked"] == len(grid) + len(extra)
                and set(books.verification["anchors"]) == {"gross", "base", "double_cost"},
                "Incomplete financial verification")
        verification = dict(books.verification, status="passed", coarse_settings=len(grid),
                            refinement_settings=len(extra))
        write_json(target / "verification.json", verification)
        write_report(target, protocol, grid, records, provenance)
        members = ("protocol.json", "grid.json", "refinements.json", "crossings.json",
                   "verification.json", "README.md", "crossings.svg", "public.json")
        receipt.update(status="passed", artifacts_sha256={n: digest((target/n).read_bytes()) for n in members})
    except Exception as exc:
        receipt.update(status="failed", error=str(exc))
        raise
    finally:
        receipt["ended_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(target / "run.json", receipt)
    print(f"Verified {len(grid)} grid settings and {len(extra)} additional cost settings.")
    print(f"Report: {target/'README.md'}\nFigure: {target/'crossings.svg'}\nReceipt: {target/'run.json'}")
    return 0
