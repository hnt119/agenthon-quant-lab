"""Frozen inputs, completed-close signals and continuous BTC/cash portfolios."""
import csv
from datetime import date, timedelta
import io
import math
from pathlib import Path

from agenthon_btc.pilot import features
from agenthon_quant.records import digest, strict_json
from agenthon_quant.trading import opening_fill, simulate_ledger

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "experiments/btc-financial-v1"
PROTOCOL = "6f22762575c834217b528961f2cd7804b4a0f99150d02adc5a6f0e25d726a6a5"
FREEZE = "e56c000e8bfa6e9ebe2854998e10af3dbe10522b"
COLUMNS = ["date","open","close","close_minute","minute_5","price_5","minute_30","price_30","positive_minutes","volume_btc"]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def frozen():
    raw = (DATA/"protocol.json").read_bytes()
    require(digest(raw)==PROTOCOL,"Protocol differs from frozen specification")
    spec = strict_json(raw)
    source = (DATA/"source.json").read_bytes()
    require(digest(source)==spec["source_manifest_sha256"],"Source identity differs")
    return spec, strict_json(source)


def read_rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode("ascii")))
    require(reader.fieldnames==COLUMNS, "Unexpected session schema")
    rows = []
    for item in reader:
        require(None not in item and None not in item.values(),"Invalid session record")
        d = date.fromisoformat(item["date"])
        require(str(d)==item["date"] and (not rows or d==date.fromisoformat(rows[-1]["date"])+timedelta(days=1)),
                "Invalid or noncontiguous UTC dates")
        row = dict(date=str(d))
        for k in COLUMNS[1:]:
            row[k] = int(item[k]) if k in ("close_minute","minute_5","minute_30","positive_minutes") else float(item[k])
        require(5<=row["minute_5"]<=row["minute_30"]<=row["close_minute"]<=1439 and row["minute_30"]>=30
                and 1<=row["positive_minutes"]<=1440 and all(math.isfinite(row[k]) and row[k]>0
                for k in ("open","close","price_5","price_30","volume_btc")),"Invalid trade proxies")
        rows.append(row)
    require(bool(rows),"No sessions")
    return rows


def signals(rows, spec):
    train_end = spec["development"][1]
    params = {**spec,"partitions":{"train":[spec["development"][0],train_end]}}
    quality = dict(price_adjustment="unadjusted", source="Bitstamp spot BTC/USD",
                   input_sha256=spec["snapshot_sha256"], timestamp_convention="session_date", session_timezone="UTC")
    obs, fit = features(rows, quality, params)
    return obs,fit


def fit_weights(obs, years):
    weights = {}
    for year in years:
        members = [x["momentum20"] for x in obs if x["date"]<f"{year}-01-01" and x["momentum20"] is not None]
        count = sum(x>0 for x in members)
        weights[year] = dict(through=f"{year-1}-12-31",valid=len(members),positive=count,weight=count/len(members))
    return weights


def rebalance(cash, shares, w, price, fee, slip):
    """Move to the desired post-cost quote-value fraction, using the same spot fill primitive."""
    gap = w*(cash+shares*price)-shares*price
    if w in (0,1):
        return opening_fill(cash,shares,w,price,fee,slip)
    if gap>0:
        mult = (1+slip)*(1+fee)
        budget = gap*mult/(1+w*(mult-1))
        _, bought, q, fill, charge, drag = opening_fill(budget,0,1,price,fee,slip)
        return cash-budget,shares+bought,q,fill,charge,drag
    if gap<0:
        mult = (1-slip)*(1-fee)
        sold = -gap/(price*(1-w*(1-mult)))
        proceeds, _, q, fill, charge, drag = opening_fill(0,sold,0,price,fee,slip)
        return cash+proceeds,shares-sold,q,fill,charge,drag
    return cash,shares,0,None,0,0


def passive(quotes, weights, initial, fee, slip):
    cash, shares, previous = initial,0.,initial
    ledger=[]
    for row in quotes:
        year = int(row["date"][:4])
        price = row["open"]
        before = cash+shares*price
        target = None
        q, fill, charge, drag = 0.,None,0.,0.
        if row["date"].endswith("-01-01"):
            target = weights[year]["weight"]
            cash,shares,q,fill,charge,drag = rebalance(cash,shares,target,price,fee/10000,slip/10000)
        equity = cash+shares*row["close"]
        ledger.append(dict(date=row["date"],cash=cash,shares=shares,trade_quantity=q,fill_price=fill,fee=charge,
                           slippage_cost=drag,exposure=shares*row["close"]/equity,equity=equity,pnl=equity-previous,
                           quoted_notional=abs(q)*price,turnover=abs(q)*price/before,target_for_open=target))
        previous=equity
    return ledger


def timestamp(day, minute):
    return f"{day}T{minute//60:02d}:{minute%60:02d}:00Z"


def books(rows, obs, weights, spec):
    first = next(i for i,r in enumerate(rows) if r["date"]==f"{spec['evaluation_years'][0]}-01-01")
    market = rows[first:]
    start = spec["initial_cash"]
    for scenario,(delay,fee,slip) in spec["scenarios"].items():
        quotes = [dict(date=r["date"],open=r[f"price_{delay}"],close=r["close"]) for r in market]
        seed = rows[first-1]
        for arm in spec["arms"]:
            if arm=="passive_mix":
                entries = passive(quotes,weights,start,fee,slip)
            else:
                targets = [s["targets"][arm] for s in obs[first-1:]]
                entries = simulate_ledger([seed,*quotes],targets,start,fee,slip)[1:]
            previous=peak=start
            for j,(e,bar) in enumerate(zip(entries,market,strict=True)):
                equity=e["equity"]
                peak=max(peak,equity)
                cutoff=timestamp(bar["date"],0)
                # A null passive target means an explicit hold with a drifting market weight.
                yield {k:e[k] for k in ("date","cash","shares","equity","trade_quantity","fill_price","fee","slippage_cost",
                         "turnover","quoted_notional","exposure","pnl","target_for_open")} | dict(
                         arm=arm,scenario=scenario,signal_session=rows[first+j-1]["date"],feature_cutoff=cutoff,
                         decision_time=cutoff,execution_proxy_time=timestamp(bar["date"],bar[f"minute_{delay}"]),
                         execution_time=timestamp(bar["date"],bar[f"minute_{delay}"]) if e["trade_quantity"] else None,
                         quote=bar[f"price_{delay}"],close=bar["close"],daily_return=equity/previous-1,
                         drawdown=1-equity/peak)
                previous=equity
