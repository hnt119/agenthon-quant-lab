"""User-facing, offline replay of the one supported frozen BTC study."""
import csv
import gzip
import math
from pathlib import Path
from uuid import uuid4

from agenthon_quant import __version__
from agenthon_quant.records import digest, strict_json, write_json
from .compatibility import COMPATIBILITY, ORIGINAL_RECEIPT, qualify
from .reader import paragraphs, write_report
from .run import execute, read_verified, sources
from .study import DATA, ROOT, frozen, require
from .view import render

SAVED = ROOT/"reports/btc-financial-v1"
RECEIPT = ORIGINAL_RECEIPT
PRESENTATION = {"tables.csv":"43d4be47d20284a3ce4fd3d1845b3fe8e3544b1e9a81a4aae1821d6ea3f9730d",
                "equity.svg":"f6322050c5d13023af4f0d5a0bb21625404390d42af6f1ea5e86282149250e1b"}


def admitted_reference():
    spec,_ = frozen()
    reference = (SAVED/"run.json").read_bytes()
    require(digest(reference)==RECEIPT, "The original study receipt differs from this toolkit version")
    reference = strict_json(reference)
    qualify(reference["code_files_sha256"], sources())
    require(digest((DATA/"sessions.csv").read_bytes())==spec["snapshot_sha256"], "Bundled BTC data hash mismatch")
    return reference


def compare(a,b):
    """Allow last-place numerical variation while requiring identical decisions and structure."""
    if type(a) is not type(b):
        return False
    if isinstance(a,dict):
        return a.keys()==b.keys() and all(compare(v,b[k]) for k,v in a.items())
    if isinstance(a,list):
        return len(a)==len(b) and all(compare(x,y) for x,y in zip(a,b))
    if isinstance(a,float):
        return math.isclose(a,b,rel_tol=2e-12,abs_tol=1e-10)
    return a==b


def decoded(path):
    if path.suffix==".csv":
        with path.open(newline="") as stream:
            return [dict((k,float(v) if k not in {"scenario","arm","period"} and v else v) for k,v in row.items())
                    for row in csv.DictReader(stream)]
    if path.name.endswith((".jsonl",".jsonl.gz")):
        op=gzip.open if path.suffix==".gz" else open
        with op(path,"rt") as stream:
            return [strict_json(line) for line in stream]
    return strict_json(path.read_bytes())


def reproduce(out=None):
    target = Path(out).expanduser().resolve() if out else Path.cwd()/"runs"/("btc-study-"+uuid4().hex[:12])
    try:
        reference = admitted_reference()
        expected = dict(reference["output_artifacts_sha256"], **PRESENTATION)
        for name,checksum in expected.items():
            require(digest((SAVED/name).read_bytes())==checksum, f"Archived artifact differs: {name}")
    except FileNotFoundError as exc:
        raise ValueError(f"Missing bundled study file {Path(exc.filename).name}. Reinstall the distribution. Restore a complete checkout of "
                         "the reviewed toolkit for source installations. The admitted daily data come with it and need no provider key.") from exc
    require(not target.exists(),f"Output folder already exists and was preserved: {target}. Omit --out for a fresh folder.")
    execute(target)
    receipt = dict(status="checking",toolkit_version=__version__,original_receipt_sha256=RECEIPT,
                   implementation_compatibility_sha256=COMPATIBILITY,artifacts={})
    try:
        verified = read_verified(target)
        render(verified,target)
        for name,checksum in expected.items():
            actual=digest((target/name).read_bytes())
            if actual==checksum:
                status="byte-identical"
            elif name!="equity.svg" and compare(decoded(SAVED/name),decoded(target/name)):
                status="numerically equivalent"
            else:
                raise ValueError(f"Frozen reproduction differs: {name}. Inspect the retained outputs in {target}")
            receipt["artifacts"][name]=dict(status=status,sha256=actual)
        write_report(target,verified)
        receipt.update(status="passed",financial_checks=verified[-1],report_sha256=digest((target/"report.md").read_bytes()),
                       dashboard_sha256=digest((target/"dashboard.html").read_bytes()))
    except Exception as exc:
        receipt.update(status="failed",error=str(exc))
        raise
    finally:
        write_json(target/"reproduction.json",receipt)
    print(f"Quant Lab {__version__} · frozen BTC study · verification passed")
    print(paragraphs(verified[1],verified[-2])[1])
    print(f"Evidence decision: {verified[-2]['decision']}. Prospective performance is unmeasured.")
    for label,name in (("Report","report.md"),("Dashboard","dashboard.html"),("Reproduction checks","reproduction.json")):
        print(f"{label}: {target/name}")
    return 0
