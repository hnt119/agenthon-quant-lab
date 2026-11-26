"""Check a completed cost study's saved evidence without invoking its simulator or search."""
from argparse import ArgumentParser
from hashlib import sha256
from itertools import groupby, pairwise
import json
from math import isfinite
from pathlib import Path


PROTOCOL_SHA256 = "02ace6a5531f2a0debd68a929a82e63137b6e04d5ee6e42b45e0ad9b78b3d3b3"
FILES = {"protocol.json", "grid.json", "refinements.json", "crossings.json",
         "verification.json", "README.md", "crossings.svg", "public.json"}
COMPARISONS = {
    "passive_sharpe": ("passive_mix", "sharpe"), "passive_wealth": ("passive_mix", "ending_equity"),
    "hold_sharpe": ("buy_and_hold", "sharpe"), "hold_wealth": ("buy_and_hold", "ending_equity"),
}


def require(condition, name):
    if not condition:
        raise ValueError(f"Cost evidence mismatch: {name}")


def differences(row):
    contrasts = {}
    for key, (arm, metric) in COMPARISONS.items():
        a, b = (row["portfolios"][p]["pooled"][metric] for p in ("momentum20", arm))
        for value in (a, b):
            require((metric == "sharpe" and value is None) or
                    (type(value) in (int, float) and isfinite(value)), f"{key} endpoint")
        contrasts[key] = None if a is None or b is None else a - b
    require(row["differences"] == contrasts, "pooled differences derived from portfolios")
    return contrasts


def check_curve(grid, values, result, tolerance, search, visited):
    """Match sampled equalities and sign changes to every reported event and trial."""
    missing = [x for x in grid if values[x] is None]
    equalities = {x for x in grid if x not in missing and abs(values[x]) <= tolerance}
    flat = [[a, b] for a, b in pairwise(grid) if a not in missing and b not in missing
            and abs(values[a] - values[b]) <= tolerance]
    require(result["undefined_samples"] == missing and result["near_flat_intervals"] == flat,
            "undefined or near-flat samples")
    intervals = []
    for is_equal, members in groupby(grid, equalities.__contains__):
        if is_equal:
            run = list(members)
            intervals.append((run[0], run[-1], True))
    intervals.extend((a, b, False) for a, b in pairwise(grid)
                     if a not in missing and b not in missing and a not in equalities and b not in equalities
                     and (values[a] > 0) != (values[b] > 0))
    events = result["events"]
    require(len(intervals) == len(events), "coarse bracket/equality coverage")
    unresolved = bool(missing)
    for (lo, hi, hit), event in zip(sorted(intervals), events, strict=True):
        kind = event["kind"]
        if hit:
            expected_kind = "sampled_equality" if lo == hi else "sampled_equal_range"
            require(event["boundary"] == (lo == grid[0] or hi == grid[-1]), "endpoint equality")
            expected_estimate = lo if lo == hi else None
        else:
            require(event["source_bracket"] == [lo, hi] and event["boundary"] is False, "source bracket")
            trials = event["trials"]
            require(len(trials) <= search["max_midpoints_per_bracket"], "trial limit")
            expected_kind = "bracketed"
            for j, (mid, val) in enumerate(trials):
                require(hi-lo > search["lambda_width_tolerance"] and mid == (lo+hi)/2 and mid in values
                        and values[mid] == val, "recorded bisection trial")
                visited.setdefault(mid, None)
                if val is None or abs(val) <= tolerance:
                    require(j == len(trials)-1, "trials after undefined or equal sample")
                    if val is None:
                        expected_kind = "undefined_refinement"
                    else:
                        lo = hi = mid
                        expected_kind = "sampled_equality"
                    break
                if (val > 0) == (values[lo] > 0):
                    lo = mid
                else:
                    hi = mid
            if expected_kind == "bracketed" and hi-lo > search["lambda_width_tolerance"]:
                require(len(trials) == search["max_midpoints_per_bracket"] or (
                    len(visited) == search["max_additional_settings"] and (lo+hi)/2 not in values),
                    "unexplained early refinement stop")
                expected_kind = "refinement_limit"
            expected_estimate = (lo+hi)/2 if expected_kind in ("sampled_equality", "bracketed") else None
        require(kind == expected_kind and event["estimate"] == expected_estimate, "crossing outcome")
        require((event["lo"], event["hi"], event["value_lo"], event["value_hi"])
                == (lo, hi, values[lo], values[hi]), "final checked endpoint values")
        unresolved |= kind in ("refinement_limit", "undefined_refinement")
    if unresolved:
        status = "incomplete"
    elif not events:
        status = "no_crossing_detected"
    elif len(events) > 1:
        status = "multiple_detected"
    else:
        status = "crossing_detected" if events[0]["kind"] == "bracketed" else "sampled_equalities"
    require(status == result["status"], "criterion status")


def check(folder):
    def read(name):
        return json.loads((folder / name).read_bytes())
    receipt = read("run.json")
    require(receipt["status"] == "passed" and receipt["study_id"] == "btc-cost-break-even-v1", "run status")
    hashes = receipt["artifacts_sha256"]
    require(set(hashes) == FILES and hashes["protocol.json"] == PROTOCOL_SHA256, "frozen artifact roster")
    for name, expected in hashes.items():
        require(sha256((folder / name).read_bytes()).hexdigest() == expected, f"{name} bytes")
    protocol = read("protocol.json")
    grid, additions, crossings = read("grid.json"), read("refinements.json"), read("crossings.json")
    points = [s["lambda"] for s in grid]
    require(points == [i/20 for i in range(41)], "all 41 coarse settings")
    samples = [*grid, *additions]
    contrasts = {}
    for s in samples:
        x = s["lambda"]
        require(type(x) in (int, float) and 0 <= x <= 2 and x not in contrasts, "unique setting in range")
        require((s["fee_bps"], s["slippage_bps"]) == (50*x, 10*x), "one-way costs")
        require(set(s["portfolios"]) == set(protocol["arms"]), "five financial books")
        periods = {"pooled", "2020", "2021", "2022", "2023", "2024"}
        require(all(set(p) == periods for p in s["portfolios"].values()), "annual and pooled coverage")
        contrasts[x] = differences(s)
    search = protocol["search"]
    require(len(additions) <= search["max_additional_settings"], "bounded new cost settings")
    require(set(crossings) == set(COMPARISONS), "all four comparisons")
    visited = {}
    for key in search["criteria_order"]:
        tol = search["sharpe_zero_tolerance"] if key.endswith("sharpe") else search["wealth_zero_tolerance_usd"]
        check_curve(points, {x: c[key] for x,c in contrasts.items()}, crossings[key], tol, search, visited)
    require(list(visited) == [s["lambda"] for s in additions], "retained refinements in first-use order")
    verify = read("verification.json")
    require(verify["status"] == "passed" and verify["settings_checked"] == len(samples)
            and verify["coarse_settings"] == len(grid) and verify["refinement_settings"] == len(additions),
            "financial verification coverage")
    public = read("public.json")
    curve = [{k:s[k] for k in ("lambda", "fee_bps", "slippage_bps", "differences")} for s in grid]
    require(public["curve"] == curve and public["crossings"] == crossings, "public exhibit")
    require(public["provenance"]["protocol_sha256"] == PROTOCOL_SHA256, "public protocol identity")
    return {"status": "passed", "coarse_settings": len(points), "refinements": len(additions),
            "comparisons": {k: v["status"] for k, v in crossings.items()}}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    print(json.dumps(check(parser.parse_args().folder), indent=2))
