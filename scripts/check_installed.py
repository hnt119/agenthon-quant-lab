"""Exercise the installed CLI with a fresh working directory, no Git and no checkout paths."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig


def check(out, exact):
    if sys.prefix == sys.base_prefix:
        raise ValueError("Use a clean virtual environment containing the built wheel")
    dist = metadata.distribution("agenthon-quant-lab")
    if json.loads(dist.read_text("direct_url.json") or "{}").get("dir_info", {}).get("editable"):
        raise ValueError("An editable installation cannot qualify a wheel")
    out = out.resolve()
    if out.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("Choose a fresh directory outside the checkout")
    out.mkdir(parents=True, exist_ok=False)
    scripts = Path(sysconfig.get_path("scripts"))
    executable = scripts / ("quant-lab.exe" if os.name == "nt" else "quant-lab")
    env = {"HOME": str(out), "PATH": str(scripts), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
           **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ}}
    def run(*args, timeout=180):
        return subprocess.run([executable, *args], cwd=out, env=env, check=True, timeout=timeout,
                              stdout=subprocess.PIPE, text=True).stdout

    assert run("--version").strip() == f"Quant Lab {dist.version}"
    doctor = json.loads(run("doctor", "--json"))
    assert doctor["installation"] == "installed distribution" and doctor["status"] == "ready"
    assert doctor["code"]["git_commit"] is None
    assert Path(doctor["code"]["source_root"]).is_relative_to(sys.prefix)
    (out / "doctor.json").write_text(json.dumps(doctor, indent=2))
    for kind in ("options", "trading", "historical"):
        assert json.loads(run("example", kind, "--out", kind))["status"] == "passed"
    run("inspect-data", "historical/spec.json")
    run("run", "options/spec.json", "--out", "manual")
    run("explain", "options")
    run("verify-inputs", "historical")
    run("reproduce", "historical", "--out", "replayed")
    run("bundle", "options", "--out", "options.zip")
    for category, query, expected in (("papers", "FFT", "fits-2023"),
                                      ("experiments", "btc-financial-research-v1", "btc-financial-research-v1")):
        results = json.loads(run("archive", category, query, "--json"))
        assert expected in {r["id"] for r in results["records"]}

    run("btc-study", "--out", "btc")
    folder = out / "btc"
    receipt = json.loads((folder / "reproduction.json").read_bytes())
    record = json.loads((folder / "run.json").read_bytes())
    assert receipt["status"] == "passed" and receipt["toolkit_version"] == dist.version
    assert record["checkout_commit"] is None and record["model_calls"] == record["paid_usd"] == 0
    assert receipt["financial_checks"]["verified_period_summaries"] == 120
    assert receipt["financial_checks"]["portfolio_sessions"] == 36540
    assert len(receipt["artifacts"]) == 8
    for name, entry in receipt["artifacts"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == entry["sha256"]
        assert entry["status"] in ({"byte-identical"} if exact else {"byte-identical", "numerically equivalent"})
    for name, key in (("report.md", "report_sha256"), ("dashboard.html", "dashboard_sha256")):
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == receipt[key]
    print(f"All CLI workflows passed on {sys.version.split()[0]}. "
          f"Byte-identical outputs: {sum(v['status'] == 'byte-identical' for v in receipt['artifacts'].values())}/8. {folder}")

    # Only the checking process reads committed expectations. The installed CLI
    # receives a fresh working directory and the same restricted environment above.
    from agenthon_financial.reproduce import compare
    run("btc-cost-break-even", "--out", "cost-study", timeout=600)
    replay = out / "cost-study"
    reference = Path(__file__).resolve().parents[1] / "reports/btc-cost-break-even-v1"
    result = json.loads((replay / "run.json").read_bytes())
    assert result["status"] == "passed" and result["checkout_commit"] is None
    assert result["software_version"] == dist.version
    for name, expected_hash in result["artifacts_sha256"].items():
        assert hashlib.sha256((replay / name).read_bytes()).hexdigest() == expected_hash
    if exact:
        archived_hashes = json.loads((reference / "run.json").read_bytes())["artifacts_sha256"]
        assert result["artifacts_sha256"] == archived_hashes
    grades = {}
    for name in ("grid.json", "refinements.json", "crossings.json", "public.json"):
        actual = (replay / name).read_bytes()
        expected = (reference / name).read_bytes()
        if actual == expected:
            grades[name] = "byte-identical"
        else:
            assert not exact and compare(json.loads(actual), json.loads(expected)), name
            grades[name] = "numerically equivalent"
    stats = json.loads((replay / "verification.json").read_bytes())
    assert stats["coarse_settings"] == 41 and stats["settings_checked"] == 41 + stats["refinement_settings"]
    assert stats["independent_totals"]["portfolio_sessions"] == stats["settings_checked"] * 9135
    print(f"Installed BTC cost study: {grades}; {stats['settings_checked']} simulated cost settings.")


    from agenthon_financial.reproduce import decoded
    from agenthon_financial.weekly_run import ARTIFACTS
    run("btc-weekly-cadence", "--out", "weekly")
    weekly = out / "weekly"
    archived = reference.parent / "btc-weekly-cadence-v1"
    receipt = json.loads((weekly / "run.json").read_bytes())
    assert receipt["status"] == "passed" and receipt["checkout_commit"] is None
    assert receipt["software_version"] == dist.version
    assert set(receipt["artifacts_sha256"]) == set(ARTIFACTS)
    for name, expected_hash in receipt["artifacts_sha256"].items():
        assert hashlib.sha256((weekly / name).read_bytes()).hexdigest() == expected_hash
    if exact:
        archived_hashes = json.loads((archived / "run.json").read_bytes())["artifacts_sha256"]
        assert receipt["artifacts_sha256"] == archived_hashes
    grades = {}
    for name in ("ledger.jsonl.gz", "metrics.json", "comparisons.json", "public.json"):
        if (weekly / name).read_bytes() == (archived / name).read_bytes():
            grades[name] = "byte-identical"
        else:
            assert not exact and compare(decoded(weekly / name), decoded(archived / name)), name
            grades[name] = "numerically equivalent"
    print(f"Installed weekly cadence study on {sys.version.split()[0]}: {grades}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--exact", action="store_true", help="Require byte identity in the recorded reference environment")
    args = parser.parse_args()
    if not __debug__:
        parser.error("Run without Python optimization so assertions remain enabled")
    check(args.out, args.exact)
