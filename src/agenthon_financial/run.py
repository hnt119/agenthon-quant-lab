"""Content-bound historical replay. A failed attempt keeps its own receipt."""
from datetime import datetime, timezone
import gzip
import json
import platform
import subprocess

import numpy
import scipy

from agenthon_btc.run import read_lines, write_lines
from agenthon_quant.records import digest, strict_json, write_json

from .analysis import analyze, labels
from .study import DATA, FREEZE, PROTOCOL, ROOT, books, fit_weights, frozen, read_rows, require, signals
from .verify import verify

ARTIFACTS=("features.jsonl","fit.json","ledger.jsonl.gz","predictions.json","metrics.json","verification.json")


def inputs():
    spec,source=frozen()
    raw=(DATA/"sessions.csv").read_bytes()
    require(digest(raw)==spec["snapshot_sha256"]==source["quality"]["sha256"],"Snapshot hash mismatch")
    return spec,read_rows(raw)


def sources():
    paths=["src/agenthon_financial/"+p+".py" for p in ("study","analysis","verify","run")]
    paths += ["src/agenthon_btc/"+p+".py" for p in ("pilot","verify","run")]
    paths += ["src/agenthon_quant/"+p+".py" for p in ("trading","spectral","records")]
    return {p:digest((ROOT/p).read_bytes()) for p in paths}


def hashes(out):
    return {p:digest((out/p).read_bytes()) for p in ARTIFACTS}


def write_ledger(path, entries):
    with path.open("xb") as fh, gzip.GzipFile(fileobj=fh,filename="",mode="wb",mtime=0) as gz:
        for e in entries:
            gz.write((json.dumps(e,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode())


def execute(out):
    spec,rows=inputs()
    out.mkdir(parents=True,exist_ok=False)
    record=dict(workflow=spec["id"],status="started",started_utc=datetime.now(timezone.utc).isoformat(),
                protocol_commit=FREEZE,protocol_sha256=PROTOCOL,input_sha256=spec["snapshot_sha256"],
                source_manifest_sha256=spec["source_manifest_sha256"],code_files_sha256=sources(),
                checkout_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,
                model_calls=0,paid_usd=0,evidence="retrospective",prospective_observations=0)
    write_json(out/"run.json",record)
    try:
        obs,fit=signals(rows,spec)
        weights=fit_weights(obs,spec["evaluation_years"])
        entries=list(books(rows,obs,weights,spec))
        predictions={str(d):labels(rows,obs,spec["evaluation_years"],d) for d in (5,30)}
        result=analyze(entries,predictions,spec)
        write_lines(out/"features.jsonl",obs)
        write_json(out/"fit.json",dict(fft=fit,annual_weights=weights))
        write_ledger(out/"ledger.jsonl.gz",entries)
        write_json(out/"predictions.json",predictions)
        write_json(out/"metrics.json",result)
        receipt=verify(rows,obs,fit,{str(k):v for k,v in weights.items()},entries,predictions,result,spec)
        write_json(out/"verification.json",receipt)
        record.update(status="passed",output_artifacts_sha256=hashes(out))
    except Exception as exc:
        record.update(status="failed",error=str(exc))
        raise
    finally:
        record["ended_utc"]=datetime.now(timezone.utc).isoformat()
        write_json(out/"run.json",record)


def read_verified(out):
    spec,rows=inputs()
    record=strict_json((out/"run.json").read_bytes())
    require(record["status"]=="passed" and record["protocol_sha256"]==PROTOCOL
            and record["protocol_commit"]==FREEZE and record["input_sha256"]==spec["snapshot_sha256"]
            and record["source_manifest_sha256"]==spec["source_manifest_sha256"]
            and record["code_files_sha256"]==sources() and record["output_artifacts_sha256"]==hashes(out),
            "Run identity or artifact hash differs")
    obs=read_lines(out/"features.jsonl")
    read=lambda p:strict_json((out/p).read_bytes())
    fit,pred,result=read("fit.json"),read("predictions.json"),read("metrics.json")
    with gzip.open(out/"ledger.jsonl.gz","rt",encoding="ascii") as f:
        entries=[strict_json(line) for line in f]
    receipt=verify(rows,obs,fit["fft"],fit["annual_weights"],entries,pred,result,spec)
    require(receipt==read("verification.json"),"Independent verification receipt differs")
    require(result==analyze(entries,pred,spec),"Saved summary, uncertainty or decision differs on replay")
    return record,spec,obs,fit,entries,result,receipt
