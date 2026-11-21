"""Extract UTC sessions from the pinned historical Bitstamp minute archive (data only)."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

SHA = "1be152060b39327b669cbed236eeb283191fadaf3862f76c1e974be54ceb1a20"
START, STOP = date(2017,1,1), date(2025,1,1)
FIELDS = ("date","open","close","close_minute","minute_5","price_5","minute_30","price_30","positive_minutes","volume_btc")


def extract(path):
    with path.open("rb") as source:
        if hashlib.file_digest(source,"sha256").hexdigest() != SHA:
            raise ValueError("Historical archive fingerprint differs")
    origin = date(1970,1,1)
    start, stop = [(d-origin).days*86400 for d in (START,STOP)]
    grid = list(range(start,stop,86400))
    records, audit = {}, Counter()
    prior = start-60
    last_price = None
    with gzip.open(path,"rt",encoding="ascii",newline="") as f:
        stream = csv.reader(f)
        if next(stream) != ["timestamp","open","high","low","close","volume"]:
            raise ValueError("Unexpected minute schema")
        for stamp,o,h,l,c,v in stream:
            ts = int(stamp)
            if ts < start or ts >= stop:
                continue
            if ts % 60 or ts <= prior:
                raise ValueError("Duplicate, off-minute or unordered timestamp")
            prior = ts
            day, minute = ts-ts%86400, ts%86400//60
            if day not in records:
                records[day] = {"labels":0,"positive_minutes":0,"volume_btc":0.0}
            d = records[day]
            d["labels"] += 1
            op,hi,lo,cl,vol = map(float,(o,h,l,c,v))
            if not all(math.isfinite(x) for x in (op,hi,lo,cl,vol)) or not (0<lo<=min(op,cl)<=max(op,cl)<=hi and vol>=0):
                raise ValueError("Invalid minute OHLCV")
            if vol == 0:
                audit["zero_volume"] += 1
                audit["nonflat_zero_volume"] += hi != lo
                continue
            audit["minute_high_low_ratio_over_1.2"] += hi/lo > 1.2
            if last_price:
                audit["successive_trade_bar_open_gap_over_20pct"] += abs(op/last_price-1) > .2
            last_price = cl
            d.setdefault("open",o)
            d["close"],d["close_minute"] = c,minute
            d["positive_minutes"] += 1
            d["volume_btc"] += vol
            for delay in (5,30):
                key = f"minute_{delay}"
                if minute>=delay and key not in d:
                    d[key],d[f"price_{delay}"] = minute,o
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=FIELDS,lineterminator="\n")
    writer.writeheader()
    missing=0
    for day in grid:
        d=records.get(day,{})
        if d.get("labels",0)<.99*1440 or "minute_30" not in d:
            raise ValueError(f"Ineligible daily coverage: {datetime.fromtimestamp(day,timezone.utc).date()}")
        missing += 1440-d["labels"]
        d["date"]=str(datetime.fromtimestamp(day,timezone.utc).date())
        writer.writerow({k:d[k] for k in FIELDS})
    raw=out.getvalue().encode()
    return raw,dict(audit,days=len(grid),expected_minutes=len(grid)*1440,missing_minutes=missing,
                    duplicates=0,invalid_ohlcv=0,unordered=0,min_labels_per_day=min(d["labels"] for d in records.values()),
                    max_fill_minute_5=max(d["minute_5"] for d in records.values()),
                    max_fill_minute_30=max(d["minute_30"] for d in records.values()),
                    sessions_filled_after_5=sum(d["minute_5"]>5 for d in records.values()),
                    sessions_filled_after_30=sum(d["minute_30"]>30 for d in records.values()),
                    sha256=hashlib.sha256(raw).hexdigest())


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    data,report=extract(args.archive)
    with args.out.open("xb") as f:
        f.write(data)
    print(json.dumps(report,sort_keys=True,indent=2))
