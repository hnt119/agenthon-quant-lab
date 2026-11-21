"""Frozen decision rule and orchestration of existing spot portfolios."""
from statistics import median

from agenthon_quant import historical, spectral, trading

ARMS = ("buy_and_hold", "cash", "momentum20", "momentum20_fft")


def features(rows, quality, spec):
    profiles = spectral.historical_profiles(rows, quality)
    if (profiles["method_id"], profiles["window_returns"]) != (spec["entropy_method"], spec["entropy_returns"]):
        raise ValueError("Changed spectral method")
    n = spec["momentum_sessions"]
    cutoff = spec["partitions"]["train"][1]
    signals, members = [], []
    for i, (row, profile) in enumerate(zip(rows, profiles["observations"], strict=True)):
        d = row["date"]
        mom = row["close"] / rows[i - n]["close"] - 1 if i >= n else None
        ent = profile["spectral_entropy"]
        signals.append({"date": d, "momentum20": mom, "entropy": ent, "entropy_status": profile["status"]})
        if d <= cutoff and profile["status"] == "ok":
            members.append({"date": d, "entropy": ent})
    if not members:
        raise ValueError("No eligible training entropy")
    threshold = median(r["entropy"] for r in members)
    for s in signals:
        live = s["date"] >= cutoff
        positive = s["momentum20"] is not None and s["momentum20"] > 0
        s["targets"] = {
            "cash": 0, "buy_and_hold": int(live), "momentum20": int(live and positive),
            "momentum20_fft": int(live and positive and s["entropy"] is not None and s["entropy"] <= threshold),
        }
    return signals, {"train_end": cutoff, "members": members, "median": threshold}


def calculate(rows, quality, spec):
    from .verify import verify
    dates = [r["date"] for r in rows]
    periods = {}
    for label in ("train", "validation", "evaluation"):
        start, end = spec["partitions"][label]
        periods[label] = (dates.index(start), dates.index(end) + 1)
    if (periods["train"][0] != 0 or periods["train"][1] != periods["validation"][0]
            or periods["validation"][1] != periods["evaluation"][0] or periods["evaluation"][1] != len(rows)):
        raise ValueError("Partitions do not cover the ordered input")
    signals, fit = features(rows, quality, spec)
    books, summaries, checks = {}, {}, []
    initial = spec["initial_cash"]
    costs = spec["frictions"]
    for arm in ARMS:
        books[arm], summaries[arm] = {}, {}
        targets = [s["targets"][arm] for s in signals]
        for treatment in ("gross", "net"):
            fee, slip = (0, 0) if treatment == "gross" else (costs["net_fee_bps_each_fill"], costs["net_adverse_slippage_bps_each_fill"])
            ledger = trading.simulate_ledger(rows, targets, initial, fee, slip)
            summary = historical._summarize(ledger, initial, periods)
            path = []
            for i, entry in enumerate(ledger):
                path.append({key: entry[key] for key in ("date", "target_for_open", "signal_date", "trade_quantity", "fill_price",
                                                         "cash", "shares", "equity", "fee", "slippage_cost", "turnover", "pnl")}
                            | {"drawdown": summary["drawdown"][i]})
            books[arm][treatment] = path
            summaries[arm][treatment] = {"full": summary["metrics"], **summary["periods"]}
            evidence = [historical._period_check(summary, ledger, initial, periods)]
            if arm in ("buy_and_hold", "cash"):
                lookback = periods["train"][1]
                evidence += trading.verify_ledger(ledger, rows, initial, fee, slip, lookback, arm)
                evidence.append(historical._benchmark_check(arm, summary["equity"], rows, initial, lookback, fee, slip))
            checks.extend(dict(c, name=f"{arm}.{treatment}.{c['name']}") for c in evidence)
    checks += verify(rows, spec, signals, fit, books, summaries)
    return {"signals": signals, "fit": fit, "books": books, "metrics": summaries, "checks": checks}
