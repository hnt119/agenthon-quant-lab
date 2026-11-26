"""Independently check the saved weekly BTC accounts, public metrics and paired intervals."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, timedelta
import gzip
from hashlib import sha256
from itertools import groupby
import json
from math import isclose, sqrt
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agenthon_financial.reproduce import compare  # Frozen baseline structure and float tolerances only.

WEEKLY_PROTOCOL = "e73695d858486f71f5bc2c0aa8ade15b5e380ed197f5c5f7ef9509fea4afa425"
PARENT_RECEIPT = "89ae5b7c13d4dfd581182a714953b59c76c7f1c6779d9bb4706c9950da3f0317"
ARTIFACTS = {"protocol.json", "ledger.jsonl.gz", "metrics.json", "comparisons.json", "verification.json",
             "README.md", "weekly-cadence.svg", "public.json"}
COMPARATORS = {"vs_daily": "momentum20", "vs_passive": "passive_mix"}


def require(condition, detail):
    if not condition:
        raise ValueError(f"Weekly-study check failed: {detail}")


def checked_bytes(path, expected):
    data = path.read_bytes()
    require(sha256(data).hexdigest() == expected, f"SHA-256 for {path.name}")
    return data


def read_books(path):
    books = defaultdict(list)
    with gzip.open(path, "rt", encoding="ascii") as stream:
        for line in stream:
            entry = json.loads(line)
            books[entry["scenario"], entry["arm"]].append(entry)
    return books


def check_summary(days, start, reported, public):
    equity = np.array([start, *(row["equity"] for row in days)])
    returns = np.diff(equity) / equity[:-1]
    peak = np.maximum.accumulate(equity)
    sd = returns.std(ddof=1)
    fees = sum(row["fee"] for row in days)
    slippage = sum(row["slippage_cost"] for row in days)
    expected = dict(total_return=equity[-1] / start - 1, ending_equity=equity[-1],
                    sharpe=returns.mean() * sqrt(365) / sd if sd else None,
                    max_drawdown=np.max((peak - equity) / peak),
                    mean_close_exposure=np.mean([r["shares"] * r["close"] / r["equity"] for r in days]),
                    turnover=sum(row["turnover"] for row in days),
                    trade_events=sum(row["trade_quantity"] != 0 for row in days),
                    fees=fees, slippage_cost=slippage, transaction_cost=fees+slippage)
    require(set(expected) == set(public), "public metric fields")
    for name, value in expected.items():
        actual = reported[name]
        if value is None:
            require(actual is None, f"undefined {name}")
        else:
            require(type(actual) in (int, float) and isclose(value, actual, rel_tol=2e-12, abs_tol=1e-10),
                    f"{days[0]['date']} {days[0]['arm']} {name}")
        require(compare(actual, public[name]), f"public {name}")


def check_wealth(books, bars, spec):
    """Compound previous-close to quote, transaction friction, then quote to close."""
    for scenario, (_, fee_bps, slip_bps) in spec["scenarios"].items():
        fee, slip = fee_bps / 10000, slip_bps / 10000
        long = False
        wealth = spec["initial_cash"]
        for row in books[scenario, "weekly20"]:
            day = date.fromisoformat(row["date"])
            prior = float(bars[day-timedelta(days=1)]["close"])
            quote, close = float(bars[day]["price_5"]), float(bars[day]["close"])
            target = long
            if day.weekday() == 0:
                target = prior > float(bars[day-timedelta(days=21)]["close"])
            if long:
                wealth *= quote / prior
            if long and not target:
                wealth *= (1-slip) * (1-fee)
            if target and not long:
                wealth /= (1+slip) * (1+fee)
            if target:
                wealth *= close / quote
            require(isclose(wealth, row["equity"], rel_tol=2e-12, abs_tol=1e-10), f"{scenario} wealth {day}")
            require((row["shares"] > 0) == target, f"{scenario} exposure {day}")
            long = target


def paired_intervals(books, spec):
    """Reconstruct actual sampled daily returns for each draw, then compute sample SD."""
    settings = spec["uncertainty"]
    rng = np.random.default_rng(settings["seed"])
    draws, block_size = settings["draws"], settings["block_sessions"]
    samples = []
    weekly = books["base", "weekly20"]
    for year in spec["evaluation_years"]:
        indices = [i for i, row in enumerate(weekly) if row["date"].startswith(str(year))]
        size = len(indices)
        begins = rng.integers(0, size, (draws, (size+block_size-1)//block_size))
        # Preserve the parent bootstrap's interleaved predictive-label RNG draws.
        # The last dated label in each year would exit across its fold boundary.
        labels = size - 1
        rng.integers(0, labels, (draws, (labels+block_size-1)//block_size))
        returns = np.array([[books["base", arm][i]["daily_return"]
                             for arm in ("weekly20", *COMPARATORS.values())] for i in indices])
        samples.append((begins, returns))
    sharpe = np.empty((draws, 3))
    for first in range(0, draws, 50):
        last = min(first+50, draws)
        annual = []
        for begins, returns in samples:
            index = (begins[first:last, :, None] + np.arange(block_size)) % len(returns)
            annual.append(returns[index.reshape(last-first, -1)[:, :len(returns)]])
        daily = np.concatenate(annual, axis=1)
        sharpe[first:last] = daily.mean(axis=1) * sqrt(365) / daily.std(axis=1, ddof=1)
    return {name: np.quantile(sharpe[:, 0]-sharpe[:, col], [.025, .975]).tolist()
            for col, name in enumerate(COMPARATORS, start=1)}


def check(out):
    receipt = json.loads((out / "run.json").read_bytes())
    require(receipt["status"] == "passed" and receipt["study_id"] == "btc-weekly-cadence-v1", "run identity")
    hashes = receipt["artifacts_sha256"]
    require(set(hashes) == ARTIFACTS and hashes["protocol.json"] == WEEKLY_PROTOCOL, "frozen artifact roster")
    for name, checksum in hashes.items():
        checked_bytes(out/name, checksum)
    spec = json.loads((out/"protocol.json").read_bytes())
    parent = ROOT / "reports/btc-financial-v1"
    source = ROOT / "experiments/btc-financial-v1"
    before = json.loads(checked_bytes(parent/"run.json", PARENT_RECEIPT))
    require(spec["source_receipt_sha256"] == PARENT_RECEIPT, "parent receipt")
    checked_bytes(source/"protocol.json", spec["source_protocol_sha256"])
    checked_bytes(source/"source.json", spec["source_manifest_sha256"])
    sessions = checked_bytes(source/"sessions.csv", spec["snapshot_sha256"])
    bars = {date.fromisoformat(row["date"]): row for row in csv.DictReader(sessions.decode("ascii").splitlines())}
    checked_bytes(parent/"ledger.jsonl.gz", before["output_artifacts_sha256"]["ledger.jsonl.gz"])
    for key in ("snapshot_sha256", "source_manifest_sha256", "source_receipt_sha256"):
        require(receipt["provenance"][key] == spec[key], key)
    require(receipt["provenance"]["protocol_sha256"] == WEEKLY_PROTOCOL, "receipt protocol")
    original = read_books(parent/"ledger.jsonl.gz")
    books = read_books(out/"ledger.jsonl.gz")
    metrics, contrasts, public = [json.loads((out/name).read_bytes())
                                 for name in ("metrics.json", "comparisons.json", "public.json")]
    roster = {(scenario, arm) for scenario in spec["scenarios"] for arm in spec["arms"]}
    require(set(books) == roster, "complete study ledger roster")
    public_ids = ("protocol_sha256", "protocol_commit", "source_receipt_sha256", "snapshot_sha256")
    require(public["provenance"] == {k: receipt["provenance"][k] for k in public_ids},
            "public provenance identities")
    verification = json.loads((out/"verification.json").read_bytes())
    require(verification["status"] == "passed" and all(
        verification["weekly"][s]["status"] == "passed" for s in spec["scenarios"]), "verification receipt")
    for summaries in (metrics, public["portfolios"]):
        require(set(summaries) == set(spec["scenarios"])
                and all(set(arms) == set(spec["arms"]) for arms in summaries.values()),
                "complete period summary roster")
    require(public["study_id"] == spec["id"] and public["scenarios"] == spec["scenarios"]
            and public["evaluation"] == spec["evaluation"], "public study identity")
    periods = {"pooled", *map(str, spec["evaluation_years"])}
    days = [str(day) for day in sorted(bars) if day.year in spec["evaluation_years"]]
    for (scenario, arm), path in books.items():
        require([row["date"] for row in path] == days, f"{scenario} {arm} dates")
        if arm != "weekly20":
            require(compare(original[scenario, arm], path), f"original baseline {scenario} {arm}")
        reports = metrics[scenario][arm]
        exhibits = public["portfolios"][scenario][arm]
        require(set(reports) == set(exhibits) == periods, f"{scenario} {arm} periods")
        opening = spec["initial_cash"]
        check_summary(path, opening, reports["pooled"], exhibits["pooled"])
        for year, entries in groupby(path, key=lambda row: row["date"][:4]):
            section = list(entries)
            require(isclose(reports[year]["starting_equity"], opening, rel_tol=2e-12, abs_tol=1e-10),
                    f"{scenario} {arm} opening wealth {year}")
            check_summary(section, opening, reports[year], exhibits[year])
            opening = section[-1]["equity"]
    check_wealth(books, bars, spec)
    require(public["comparisons"] == contrasts, "published comparisons")
    for scenario in spec["scenarios"]:
        for period in periods:
            for name, arm in COMPARATORS.items():
                expected = metrics[scenario]["weekly20"][period]["sharpe"] - metrics[scenario][arm][period]["sharpe"]
                require(contrasts["contrasts"][scenario][period][name] == expected, f"{scenario} {period} {name}")
    states = {(True, True): "both_long", (False, False): "both_cash",
              (True, False): "weekly_only", (False, True): "daily_only"}
    counts = Counter(states[a["shares"] > 0, b["shares"] > 0]
                     for a, b in zip(books["base", "weekly20"], books["base", "momentum20"], strict=True))
    require(counts == contrasts["position_days"], "paired exposure counts")
    mondays = [day for day in days if date.fromisoformat(day).weekday() == 0]
    require(len(mondays) == contrasts["scheduled_opportunities"] and mondays[0] == contrasts["first_opportunity"],
            "weekly opportunities")
    first_fill = next((r["date"] for r in books["base", "weekly20"] if r["trade_quantity"]), None)
    require(first_fill == contrasts["first_fill"], "first fill")
    bands = paired_intervals(books, spec)
    for key, value in bands.items():
        require(np.allclose(value, contrasts["interval95"][key], rtol=1e-12, atol=1e-12), f"{key} interval")
    return dict(status="passed", artifact_hashes=len(hashes), baseline_paths=len(books)-len(spec["scenarios"]),
                portfolio_summaries=len(books)*len(periods), weekly_marks=len(days)*len(spec["scenarios"]),
                position_days=dict(counts), paired_draws=spec["uncertainty"]["draws"], interval95=bands)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path, help="A completed btc-weekly-cadence study directory")
    args = parser.parse_args()
    print(json.dumps(check(args.output_directory), indent=2))
