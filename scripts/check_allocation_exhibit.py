"""Trace a completed allocation exhibit to its daily books and frozen comparators."""
import argparse
import calendar
from datetime import date, timedelta
from itertools import accumulate, groupby, pairwise
import json
from math import fsum
from pathlib import Path
from xml.etree import ElementTree

from check_weekly_study import check_summary, checked_bytes, compare, read_books


ROOT = Path(__file__).resolve().parents[1]
STUDY = "btc-weekly-allocation-v1"
PROTOCOL = "46cbfbee2ef6aaa5e3bc5c184340c919d07babe97d0110fed2948157c3bb0f70"
ARTIFACTS = {"protocol.json", "ledger.jsonl.gz", "metrics.json", "comparisons.json",
             "verification.json", "README.md", "drawdown.svg", "public.json"}
FOCUS = ("target50", "half_funded")
BASELINES = ("weekly20", "momentum20", "passive_mix")


def check_equal(actual, expected, name):
    if not compare(actual, expected):
        raise ValueError(f"Allocation exhibit differs: {name}")


def losses(rows, initial):
    wealth = [r["cash"] + r["shares"] * r["close"] for r in rows]
    peaks = list(accumulate(wealth, max, initial=initial))[1:]
    drops = [1 - value / peak for value, peak in zip(wealth, peaks, strict=True)]
    trough = drops.index(max(drops))  # First occurrence of the worst loss.
    peak = next((i for i in range(trough, -1, -1) if wealth[i] == peaks[trough]), None)
    def exposure(i):
        return rows[i]["shares"] * rows[i]["close"] / wealth[i]
    opening = str(date.fromisoformat(rows[0]["date"]) - timedelta(days=1))
    return drops, dict(peak_date=rows[peak]["date"] if peak is not None else opening,
                       peak_exposure=exposure(peak) if peak is not None else 0.,
                       trough_date=rows[trough]["date"], trough_exposure=exposure(trough),
                       drawdown=drops[trough])


def check_trading(books, frozen_weekly, scenario, fees, slip, diagnostics):
    target, sleeve = (books[scenario, arm] for arm in FOCUS)
    first = [next(r for r in path if r["trade_quantity"] > 0) for path in (target, sleeve)]
    check_equal(first[0]["date"], first[1]["date"], "shared first purchase")
    weights = [1 / (1 + r["cash"] / (r["shares"] * r["quote"])) for r in first]
    check_equal(diagnostics["first_fill"], dict(date=first[0]["date"], target50_weight=weights[0],
                half_funded_weight=weights[1], difference_pp=100*(weights[0]-weights[1])), "first weights")

    decisions = [r for r in frozen_weekly if r["target_for_open"] is not None]
    dates = {b["date"] for a, b in pairwise(decisions) if a["target_for_open"] == b["target_for_open"] == 1}
    trades = [(previous, row) for previous, row in pairwise(target) if row["date"] in dates]
    fills = [r for _, r in trades if r["trade_quantity"]]
    turnover = fsum(abs(r["trade_quantity"])*r["quote"] / (p["cash"] + p["shares"]*r["quote"]) for p, r in trades)
    check_equal(diagnostics["unchanged_positive"], dict(
        decisions=len(dates), fills=len(fills), buys=sum(r["trade_quantity"] > 0 for r in fills),
        sells=sum(r["trade_quantity"] < 0 for r in fills), turnover=turnover,
        fees_usd=fsum(abs(r["trade_quantity"])*r["fill_price"]*fees for r in fills),
        slippage_usd=fsum(abs(r["trade_quantity"])*r["quote"]*slip for r in fills)), "unchanged signals")


def check_figure(path, points, episodes):
    svg = ElementTree.parse(path)
    grid = svg.findall(".//{*}line[@class='grid']")
    left, right = (float(grid[0].get(k)) for k in ("x1", "x2"))
    top, bottom = min(float(e.get("y1")) for e in grid), max(float(e.get("y1")) for e in grid)
    ticks = [float(e.text[:-1]) for e in svg.findall(".//{*}text") if (e.text or "").endswith("%")]
    if min(ticks) != 0 or max(ticks) <= 0 or left >= right or top >= bottom:
        raise ValueError("Invalid drawdown chart axes")
    start, end = (date.fromisoformat(points[i]["date"]) for i in (0, -1))
    def position(day, loss):
        x = left + (right-left)*(date.fromisoformat(day)-start).days / (end-start).days
        y = top + (bottom-top)*loss*100/max(ticks)
        return x, y
    def check_point(actual, expected):
        if any(abs(a-b) > .00501 for a, b in zip(actual, expected, strict=True)):
            raise ValueError("Drawdown figure coordinates differ at displayed precision")
    lines = svg.findall(".//{*}polyline")
    markers = svg.findall(".//{*}circle")
    for arm, line, mark in zip(FOCUS, lines, markers, strict=True):
        if arm not in line.get("class", "").split():
            raise ValueError("Drawdown figure has the wrong series")
        coords = [tuple(map(float, pair.split(","))) for pair in line.get("points").split()]
        for xy, row in zip(coords, points, strict=True):
            check_point(xy, position(row["date"], row[arm]))
        episode = episodes[arm]
        check_point((float(mark.get("cx")), float(mark.get("cy"))),
                    position(episode["trough_date"], episode["drawdown"]))


def check(out):
    def read(name):
        return json.loads((out/name).read_bytes())
    receipt, public, metrics, comparisons = map(read, ("run.json", "public.json", "metrics.json", "comparisons.json"))
    check_equal(receipt["status"], "passed", "run status")
    hashes = receipt["artifacts_sha256"]
    if set(hashes) != ARTIFACTS or hashes["protocol.json"] != PROTOCOL:
        raise ValueError("Unexpected allocation artifact roster or protocol")
    for name, digest in hashes.items():
        checked_bytes(out/name, digest)
    spec = read("protocol.json")
    checked_bytes(ROOT/"experiments"/STUDY/"protocol.json", PROTOCOL)
    baseline_path = ROOT/"reports/btc-weekly-cadence-v1/ledger.jsonl.gz"
    checked_bytes(baseline_path, spec["weekly_ledger_sha256"])
    frozen, books = read_books(baseline_path), read_books(out/"ledger.jsonl.gz")
    check_equal(public["provenance"], {k: receipt["provenance"][k] for k in
                ("protocol_commit", "protocol_sha256", "snapshot_sha256")}, "provenance")
    check_equal(public["study_id"], spec["id"], "study identity")
    for key in ("evaluation", "scenarios", "scenario_units", "uncertainty"):
        check_equal(public[key], spec[key], key)
    check_equal(public["primary"], comparisons["primary"], "primary")
    check_equal(public["diagnostics"], comparisons["diagnostics"], "diagnostics")
    if set(books) != {(s, a) for s in spec["scenarios"] for a in spec["arms"]}:
        raise ValueError("Unexpected allocation ledger roster")
    verification = read("verification.json")
    check_equal(verification["status"], "passed", "verification")
    check_equal(comparisons["primary"]["interval95_pp"], verification["primary"]["interval95_pp"],
                "independent paired interval")
    base_losses = {}
    for scenario, (_, fee_bps, slip_bps) in spec["scenarios"].items():
        details = public["diagnostics"][scenario]
        check_trading(books, frozen[scenario, "weekly20"], scenario, fee_bps/10000, slip_bps/10000, details)
        for arm in spec["arms"]:
            path = books[scenario, arm]
            if arm in BASELINES:
                check_equal(path, frozen[scenario, arm], f"frozen {scenario} {arm} daily ledger")
            drops, episode = losses(path, spec["initial_cash"])
            check_equal(details["worst_declines"][arm], episode, f"{scenario} {arm} worst episode")
            if scenario == "base" and arm in FOCUS:
                base_losses[arm] = dict(zip((r["date"] for r in path), drops, strict=True))
            saved, shown = metrics[scenario][arm], public["portfolios"][scenario][arm]
            if set(saved) != {"pooled", *map(str, spec["evaluation_years"])} or set(saved) != set(shown):
                raise ValueError(f"Incomplete period coverage for {scenario} {arm}")
            opening = spec["initial_cash"]
            check_summary(path, opening, saved["pooled"], shown["pooled"])
            for year, days in groupby(path, key=lambda r: r["date"][:4]):
                segment = list(days)
                check_summary(segment, opening, saved[year], shown[year])
                opening = segment[-1]["equity"]

    episodes = public["diagnostics"]["base"]["worst_declines"]
    difference = 100 * (episodes["half_funded"]["drawdown"] - episodes["target50"]["drawdown"])
    check_equal(public["primary"]["difference_pp"], difference, "paired drawdown difference")
    special = {episodes[arm][k] for arm in FOCUS for k in ("peak_date", "trough_date")}
    special.update(spec["evaluation"])
    points = []
    for day in base_losses["target50"]:
        stamp = date.fromisoformat(day)
        if day in special or stamp.day == calendar.monthrange(stamp.year, stamp.month)[1]:
            points.append({"date": day, **{arm: base_losses[arm][day] for arm in FOCUS}})
    check_equal(public["drawdown"]["points"], points, "all public drawdown samples")
    check_figure(out/"drawdown.svg", points, episodes)
    return dict(status="passed", artifacts=len(hashes), frozen_paths=len(BASELINES)*len(spec["scenarios"]),
                period_summaries=len(books)*(1+len(spec["evaluation_years"])),
                chart_dates=len(points), series=len(FOCUS), trough_markers=len(FOCUS))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(check(parser.parse_args().directory), indent=2))
