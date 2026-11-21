"""Manually timestamp one signal, with no execution path or outcome estimates."""
from datetime import datetime, timedelta, timezone
import json

from agenthon_quant.records import digest, strict_json
from .study import DATA, PROTOCOL, frozen, read_rows, require, signals


def observation(snapshot: bytes, provenance: bytes, now: datetime):
    spec,original=frozen()
    source=strict_json(provenance)
    raw=(DATA/"sessions.csv").read_bytes()
    require(digest(raw)==spec["snapshot_sha256"] and snapshot.startswith(raw),
            "Provide an append-only extension of the frozen source history")
    require(digest(snapshot)==source["quality"]["sha256"],"Input does not match source manifest")
    require(all(source.get(k)==original[k] for k in ("venue","price_definition")),"Incompatible venue or session definitions")
    for key in ("repository_revision","attribution","url","license","license_url","retrieved_completed_utc"):
        require(isinstance(source.get(key),str) and source[key].strip(),f"Missing source field {key}")
    retrieved=datetime.fromisoformat(source["retrieved_completed_utc"])
    require(retrieved.tzinfo is not None and retrieved<=now,"Invalid acquisition time")
    rows=read_rows(snapshot)
    require(source["quality"].get("days")==len(rows),"Source session count differs")
    last=rows[-1]["date"]
    cutoff=datetime.fromisoformat(last).replace(tzinfo=timezone.utc)+timedelta(days=1)
    require(cutoff<=now and cutoff<=retrieved,"Latest snapshot session must have completed before acquisition")
    eligible=cutoff+timedelta(minutes=5)
    freeze=datetime.fromisoformat(spec["frozen_utc"])
    obs,fit=signals(rows,{**spec,"snapshot_sha256":digest(snapshot)})
    return dict(status="prospective intent" if freeze<=cutoff<=now<eligible else "retrospective backfill",
                study=spec["id"],protocol_sha256=PROTOCOL,frozen_utc=spec["frozen_utc"],
                snapshot_sha256=digest(snapshot),source_manifest_sha256=digest(provenance),
                as_of=now.isoformat(),last_completed_session=last,information_cutoff=cutoff.isoformat(),
                earliest_execution=eligible.isoformat(),execution_convention=spec["execution"],
                observation=obs[-1],fixed_entropy_threshold=fit["median"],realized_performance=None)


def record(snapshot,source,out):
    result=observation(snapshot.read_bytes(),source.read_bytes(),datetime.now(timezone.utc))
    # Calculation latency can move a near-boundary intent past its eligible quote.
    recorded=datetime.now(timezone.utc)
    result["recorded_utc"]=recorded.isoformat()
    if recorded>=datetime.fromisoformat(result["earliest_execution"]):
        result["status"]="retrospective backfill"
    with out.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    return result
