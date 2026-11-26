#!/usr/bin/env python3
"""Generate a deterministic, reviewed static projection; never copy raw evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agenthon_quant.options import run as price_options

PAPER_FIELDS = {"id", "title", "authors", "year", "year_basis", "venue_year", "url", "topics", "mechanism",
                "financial_workbench", "reported_findings", "project_relevance", "adaptation_status", "implementation", "experiment_ids", "limitations", "decision"}
EXPERIMENT_FIELDS = {"id", "title", "date", "evidence_category", "status", "topics", "paper_ids", "hypothesis", "baseline",
                     "code_commit", "protocol", "model", "configuration", "result", "usage", "limitations", "sources", "decision", "reproduction", "paper_relation"}
CATEGORIES = {"retrospective_market", "official_reported", "local_live", "synthetic", "incomplete", "not_run"}
STATUSES = {"inconclusive", "passed", "failed", "mixed", "incomplete", "not_run", "unknown"}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public_value(value):
    """A narrow content guard complements human publication review."""
    if isinstance(value, dict):
        forbidden = {"api_key", "password", "secret", "authorization", "private_key", "raw_capture", "raw_response", "reference_answer", "canary"}
        if forbidden & {key.lower() for key in value}:
            raise ValueError("A private payload field cannot enter the public projection")
        for child in value.values():
            public_value(child)
    elif isinstance(value, list):
        for child in value:
            public_value(child)
    elif isinstance(value, str):
        if re.search(r"/Users/|/private/|/home/|[A-Za-z]:\\|\b(?:localhost|127\.0\.0\.1)\b|(?:gh[pousr]_|sk-)[A-Za-z0-9_-]{20,}|-----BEGIN .*PRIVATE KEY", value):
            raise ValueError("A local path or credential-like value cannot enter the public projection")


def projection(root: Path = ROOT):
    paths = ["research/papers.json", "experiments/experiments.json"]
    raw = {name: (root / name).read_bytes() for name in paths}
    papers = json.loads(raw[paths[0]])["papers"]
    experiments = json.loads(raw[paths[1]])["experiments"]
    paper_ids = {p["id"] for p in papers}
    experiment_ids = {e["id"] for e in experiments}
    if len(paper_ids) != len(papers) or len(experiment_ids) != len(experiments):
        raise ValueError("Archive IDs must be unique")
    for paper in papers:
        if not {"id", "title", "authors", "year", "url", "topics", "adaptation_status", "limitations", "experiment_ids"} <= paper.keys():
            raise ValueError("Incomplete paper record")
        if paper["adaptation_status"] not in {"implemented", "inspiration", "proposed", "deferred"}:
            raise ValueError("Unknown adaptation status")
        if not set(paper["experiment_ids"]) <= experiment_ids:
            raise ValueError("Paper references an unknown experiment")
        if not paper["url"].startswith("https://"):
            raise ValueError("Paper needs a canonical HTTPS source")
    for experiment in experiments:
        if not {"id", "title", "evidence_category", "status", "result", "usage", "sources", "limitations", "paper_ids"} <= experiment.keys():
            raise ValueError("Incomplete experiment record")
        if experiment["status"] not in STATUSES or experiment["evidence_category"] not in CATEGORIES:
            raise ValueError("Unknown experimental evidence category or status")
        if not set(experiment["paper_ids"]) <= paper_ids:
            raise ValueError("Experiment references an unknown paper")
        if experiment["evidence_category"] == "not_run" and experiment["status"] != "not_run":
            raise ValueError("An unrun proposal must remain NOT_RUN")
    result = {"schema_version": 1,
              "provenance": {"repository": "https://github.com/hnt119/agenthon-quant-lab", "generator": "scripts/export_site.py",
                             "canonical_files_sha256": {name: sha(data) for name, data in raw.items()},
                             "scope": "Original summaries and identity metadata only; no original captures, graders, answers or PDFs"},
              "papers": [{key: value for key, value in p.items() if key in PAPER_FIELDS} for p in papers],
              "experiments": [{key: value for key, value in e.items() if key in EXPERIMENT_FIELDS} for e in experiments]}
    public_value(result)
    return result


PROGRAMME_FIELDS = {
    "id", "title", "question", "execution_state", "finding", "evidence_type", "experiment_id",
    "dataset", "evaluation_period", "comparators", "protocol_url", "implementation_url",
    "result_url", "source_receipt_url", "dependencies", "next_action",
}
STUDY_EVIDENCE = ("experiment_id", "dataset", "evaluation_period", "protocol_url",
                  "implementation_url", "result_url", "source_receipt_url", "finding")


def programme_projection(root: Path = ROOT):
    path = "research/programme.json"
    raw = (root / path).read_bytes()
    catalogue = json.loads(raw)
    if set(catalogue) != {"schema_version", "studies"} or catalogue["schema_version"] != 1:
        raise ValueError("Unknown programme schema")
    studies = catalogue["studies"]
    ids = {study["id"] for study in studies}
    if len(ids) != len(studies) or any(not re.fullmatch(r"[a-z][a-z0-9-]*", id_) for id_ in ids):
        raise ValueError("Invalid or duplicate programme ID")
    for study in studies:
        if set(study) != PROGRAMME_FIELDS:
            raise ValueError("Unexpected programme fields")
        if not set(study["dependencies"]) <= ids - {study["id"]}:
            raise ValueError("Invalid programme dependency")
        if study["execution_state"] == "proposed":
            if study["evidence_type"] != "none" or any(study[k] is not None for k in STUDY_EVIDENCE):
                raise ValueError("Proposed studies cannot carry measured outcomes")
        elif study["execution_state"] == "completed":
            if study["evidence_type"] != "retrospective" or not all(study[k] for k in STUDY_EVIDENCE):
                raise ValueError("Completed studies need identifiable evidence")
            for key in ("protocol_url", "result_url", "implementation_url", "source_receipt_url"):
                url = study[key]
                match = re.fullmatch(r"https://github\.com/hnt119/agenthon-quant-lab/blob/[0-9a-f]{40}/([a-zA-Z0-9_./-]+)", url)
                if not match or ".." in Path(match[1]).parts or not (root / match[1]).is_file():
                    raise ValueError(f"Invalid programme evidence link: {key}")
        else:
            raise ValueError("Unknown programme execution state")
    public_value(catalogue)
    return {**catalogue, "provenance": {"generator": "scripts/export_site.py",
            "canonical_files_sha256": {path: sha(raw)},
            "scope": "Editorial study descriptions. Each completed comparison links to its protocol, report and run receipt."}}


def cost_study_export(root: Path = ROOT):
    """Copy only the reviewed exhibit, bound to its qualified run receipt."""
    folder = root / "reports/btc-cost-break-even-v1"
    receipt = json.loads((folder / "run.json").read_bytes())
    data = (folder / "public.json").read_bytes()
    expected = "c9c243f2fa417243f1dcac7c6b8dd4b698163b95b0c518a47112a75994312a3f"
    if (receipt["status"] != "passed" or receipt["study_id"] != folder.name
            or receipt["artifacts_sha256"]["public.json"] != expected or sha(data) != expected):
        raise ValueError("Cost exhibit differs from the qualified study")
    public_value(json.loads(data))
    return data


def numerical_reference():
    cases = []
    base = {"spot": 100.0, "strike": 100.0, "years": 1.0, "rate": 0.05, "volatility": 0.2}
    values = [base, {**base, "years": 0}, {**base, "years": 0, "spot": 80}, {**base, "years": 0, "spot": 120},
              {**base, "volatility": 0}, {**base, "volatility": 0, "rate": -0.02}, {**base, "rate": 0},
              {**base, "years": 1e-8}, {**base, "spot": 1}, {**base, "strike": 10000},
              {**base, "spot": 10000, "strike": 1}, {**base, "years": 30, "rate": -.5, "volatility": 5},
              {**base, "years": 30, "rate": -.5, "volatility": .2}, {**base, "years": 30, "rate": .5, "volatility": 5}]
    generator = random.Random(20261114)
    for _ in range(50):
        values.append({"spot": generator.uniform(10, 500), "strike": generator.uniform(10, 500),
                       "years": generator.uniform(.01, 5), "rate": generator.uniform(-.05, .15), "volatility": generator.uniform(.01, 1)})
    for i, inputs in enumerate(values):
        spec = {"workflow": "options", "spot": inputs["spot"], "strike": inputs["strike"], "maturity_years": inputs["years"],
                "rate": inputs["rate"], "volatility": inputs["volatility"], "dividend_yield": 0, "currency": "USD", "option_type": "both"}
        analysis = price_options(spec)
        if any(check["status"] == "failed" for check in analysis["checks"]):
            raise ValueError(f"Reference case bsm-{i:03d} failed Python validation")
        cases.append({"id": f"bsm-{i:03d}", "inputs": inputs,
                      "expected": {side: float(f"{values['price']:.12g}") for side, values in analysis["results"]["valuations"].items()},
                      "python_check_counts": {status: sum(c["status"] == status for c in analysis["checks"]) for status in ("passed", "failed", "unavailable")}})
    return {"schema_version": 1, "seed": 20261114,
            "reference": "agenthon_quant.options analytic Black–Scholes–Merton with zero continuous dividend yield; checker applicability is recorded per case",
            "browser_method": "Abramowitz–Stegun 26.2.17 normal CDF; compare absolute error <= 7.5e-8*(spot+discounted strike) plus floating-point allowance",
            "reference_source_sha256": sha((ROOT / "src/agenthon_quant/options.py").read_bytes()), "cases": cases}


def check_reference(saved, current):
    """Check a frozen numerical corpus across libm/SciPy builds, without rewriting it."""
    differences = []
    if saved.keys() != current.keys() or encoded({k: v for k, v in saved.items() if k != "cases"}) != encoded({k: v for k, v in current.items() if k != "cases"}):
        raise ValueError("Pricing reference metadata or source identity changed")
    if len(saved["cases"]) != len(current["cases"]):
        raise ValueError("Pricing reference case count changed")
    for before, after in zip(saved["cases"], current["cases"]):
        if before.keys() != after.keys() or any(encoded(before[k]) != encoded(after[k]) for k in before if k not in {"expected", "python_check_counts"}):
            raise ValueError("Pricing reference inputs or case identity changed")
        if before["expected"].keys() != after["expected"].keys():
            raise ValueError("Pricing reference output schema changed")
        for side, value in before["expected"].items():
            actual = after["expected"][side]
            if type(value) not in (int, float) or type(actual) not in (int, float) or not math.isfinite(value) or not math.isfinite(actual) or not math.isclose(value, actual, rel_tol=1e-11, abs_tol=1e-12):
                raise ValueError(f"Pricing reference value drift: {before['id']} {side}: {value!r} -> {actual!r}")
            if value != actual:
                differences.append({"case": before["id"], "field": side, "saved": value, "current": actual, "absolute_difference": abs(value-actual)})
        a, b = before["python_check_counts"], after["python_check_counts"]
        if any(set(counts) != {"passed", "failed", "unavailable"} or any(type(v) is not int or v < 0 for v in counts.values()) or counts["failed"] != 0 for counts in (a, b)) or sum(a.values()) != sum(b.values()):
            raise ValueError("Pricing reference checker failure or schema changed")
        if a != b:
            raise ValueError(f"Checker applicability changed for {before['id']}: {a!r} -> {b!r}; requires separate investigation")
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in projection has drifted")
    parser.add_argument("--site-root", type=Path, help="Copy the checked projection into an existing portfolio checkout")
    args = parser.parse_args()
    outputs = {"archive.json": encoded(projection()), "programme.json": encoded(programme_projection()),
               "pricing-reference.json": encoded(numerical_reference()), "btc-cost-break-even.json": cost_study_export()}
    directory = ROOT / "site-export"
    if args.check:
        for name, data in outputs.items():
            if not (directory / name).is_file():
                parser.exit(2, f"Missing frozen projection: site-export/{name}\n")
            saved = (directory / name).read_bytes()
            if saved != data:
                if name != "pricing-reference.json":
                    parser.exit(2, f"Projection drift: site-export/{name}; regenerate with scripts/export_site.py\n")
                try:
                    differences = check_reference(json.loads(saved), json.loads(data))
                except (ValueError, KeyError, TypeError) as exc:
                    parser.exit(2, f"Projection drift: {exc}\n")
                print(json.dumps({"reference_comparison": "within_explicit_tolerance", "differences": differences}, indent=2))
            outputs[name] = saved
    else:
        directory.mkdir(exist_ok=True)
        for name, data in outputs.items():
            (directory / name).write_bytes(data)
    if args.site_root:
        site = args.site_root.resolve()
        if not (site / "public").is_dir() or not (site / "package.json").is_file():
            parser.exit(2, "--site-root must be an existing portfolio source checkout\n")
        target = site / "public/agenthon-quant-lab"
        target.mkdir(exist_ok=True)
        for name, data in outputs.items():
            (target / name).write_bytes(data)
    print(json.dumps({"status": "verified" if args.check else "generated", "files": {name: sha(data) for name, data in outputs.items()}}, indent=2))


if __name__ == "__main__":
    main()
