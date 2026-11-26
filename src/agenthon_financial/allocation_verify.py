"""Independent accounting and paired drawdown checks on the frozen spot accounts."""
from collections import defaultdict
from datetime import date
from itertools import pairwise
from math import floor, isfinite

import numpy as np

from .cost_verify import _check_period, _fields, _position
from .verify import equal


_ARMS = ("weekly20", "momentum20", "passive_mix", "target50", "half_funded")
_WEEKLY = frozenset(("weekly20", "target50", "half_funded"))


def _market_schedule(rows, years):
    """Derive signal and annual passive weights solely from the dated closes."""
    days = [date.fromisoformat(bar["date"]) for bar in rows]
    if any((b - a).days != 1 for a, b in pairwise(days)):
        raise ValueError("Source dates must be contiguous UTC sessions")
    positive = [None if i < 20 else bar["close"] > rows[i - 20]["close"]
                for i, bar in enumerate(rows)]
    weights = {}
    for year in years:
        past = [p for d, p in zip(days, positive) if d.year < year and p is not None]
        if not past:
            raise ValueError(f"Missing prior closes for the {year} passive weight")
        weights[year] = sum(past) / len(past)
    schedule = []
    for i, day in enumerate(days):
        if day.year not in years:
            continue
        if i < 21 or rows[i - 1]["date"] >= day.isoformat():
            raise ValueError("Missing the completed signal before the evaluation open")
        schedule.append((day, rows[i], rows[i - 1]["date"], int(positive[i - 1])))
    equal({d.year for d, *_ in schedule}, set(years), "evaluation year coverage")
    return schedule, weights


def _check_account(arm, schedule, weights, spec, scenario, path, periods):
    start = spec["initial_cash"]
    reserve = start / 2 if arm == "half_funded" else 0.
    active_cash, shares = start - reserve, 0.
    prior = peak = start
    by_year = defaultdict(list)
    first_fill = None
    last_weekly_target = None
    fills = 0
    delay, fee_bps, slippage_bps = spec["scenarios"][scenario]
    if delay != 5:
        raise ValueError("The frozen schedule requires the five-minute quote")
    fee_rate, slip_rate = fee_bps / 10_000, slippage_bps / 10_000
    for (day, bar, prior_day, positive), record in zip(schedule, path, strict=True):
        quote, close, minute = bar["price_5"], bar["close"], bar["minute_5"]
        if not 5 <= minute <= 1439:
            raise ValueError(f"Ineligible fill proxy on {day}")
        decision = arm not in _WEEKLY or day.weekday() == 0
        if arm == "passive_mix":
            target = weights[day.year] if (day.month, day.day) == (1, 1) else None
        elif decision:
            target = positive * (.5 if arm == "target50" else 1.)
        else:
            target = None

        # The independent solver works from post-fill equity. The production
        # engine budgets a buy or determines how many units to sell instead.
        pre_equity = reserve + active_cash + shares * quote
        pre_weight = shares * quote / pre_equity
        unchanged = arm == "target50" and last_weekly_target == (target, quote)
        instruction = None if unchanged else target
        active_cash, shares, qty, price = _position(
            active_cash, shares, instruction, quote, fee_rate, slip_rate)
        if decision and arm == "target50":
            last_weekly_target = (target, quote)
        cash = reserve + active_cash
        post_equity = cash + shares * quote
        equity = cash + shares * close
        peak = max(peak, equity)
        label = f"{scenario} {arm} {day}"
        if (target is None or unchanged) and record.get("trade_quantity") != 0:
            raise ValueError(f"Unexpected {label} trade_quantity during hold")
        if target == 0 and record.get("shares") != 0:
            raise ValueError(f"Nonzero {label} shares after a cash decision")
        cutoff = f"{day}T00:00:00Z" if decision else None
        proxy = f"{day}T{minute // 60:02d}:{minute % 60:02d}:00Z"
        _fields(record, dict(
            date=str(day), scenario=scenario, arm=arm, quote=quote, close=close,
            decision_time=cutoff, feature_cutoff=cutoff,
            signal_session=prior_day if decision else None, target_for_open=target,
            execution_proxy_time=proxy, execution_time=proxy if qty else None,
            trade_quantity=qty, fill_price=price, fee=abs(qty)*(price or 0.)*fee_rate,
            slippage_cost=abs(qty)*quote*slip_rate, quoted_notional=abs(qty)*quote,
            turnover=abs(qty)*quote/pre_equity, shares=shares, cash=cash,
            equity=equity, exposure=shares*close/equity, pnl=equity-prior,
            daily_return=equity/prior-1, drawdown=1-equity/peak,
        ), label)
        actual_quote_equity = record["cash"] + record["shares"] * quote
        equal(pre_equity - actual_quote_equity, record["fee"] + record["slippage_cost"],
              f"{label} wealth loss at execution")
        if target is not None:
            expected_weight = shares * quote / post_equity
            equal(record["shares"] * quote / actual_quote_equity, expected_weight,
                  f"{label} post-cost BTC weight at raw quote")
        if qty:
            fills += 1
            if first_fill is None:
                first_fill = dict(date=str(day), pre_weight=pre_weight,
                                  post_weight=shares * quote / post_equity)
        by_year[str(day.year)].append(record)
        prior = equity

    equal(set(periods), set(by_year) | {"pooled"}, f"{arm} summary periods")
    _check_period(path, start, periods["pooled"], f"{arm} pooled")
    for year, section in by_year.items():
        _check_period(section, start, periods[year], f"{arm} {year}")
        start = section[-1]["equity"]
    return dict(sessions=len(path), fills=fills, period_summaries=len(periods), first_fill=first_fill)


def verify_allocation(rows, spec, scenario, paths, metrics):
    """Reconstruct the five books without using the submitted decisions or balances."""
    equal(set(paths), set(_ARMS), "allocation ledger arms")
    equal(set(metrics), set(_ARMS), "allocation summary arms")
    schedule, weights = _market_schedule(rows, spec["evaluation_years"])
    accounts = {arm: _check_account(arm, schedule, weights, spec, scenario, paths[arm], metrics[arm])
                for arm in _ARMS}
    prior_full = spec["initial_cash"]
    reserve = prior_full / 2
    for full, control in zip(paths["weekly20"], paths["half_funded"], strict=True):
        context = f'{scenario} {full["date"]} half-funded'
        equal(control["equity"], reserve + .5*full["equity"], context + " total wealth identity")
        equal(control["cash"], reserve + .5*full["cash"], context + " inactive reserve")
        equal(control["shares"], .5*full["shares"], context + " sleeve units")
        multiplier = (.5*prior_full) / (reserve + .5*prior_full)
        equal(control["daily_return"], multiplier*full["daily_return"], context + " return identity")
        prior_full = full["equity"]

    first_target = accounts["target50"]["first_fill"]
    first_control = accounts["half_funded"]["first_fill"]
    first_difference = None
    if first_target is not None or first_control is not None:
        if first_target is None or first_control is None or first_target["date"] != first_control["date"]:
            raise ValueError("First allocation purchases did not coincide")
        _, fee, slip = spec["scenarios"][scenario]
        # The fully invested sleeve buys $5,000 / k of BTC at the quote.
        k = (1 + fee / 10_000)*(1 + slip / 10_000)
        equal(first_control["post_weight"], 1/(1+k), "control first-fill weight")
        equal(first_target["post_weight"], .5, "target first-fill weight")
        first_difference = 100*(first_target["post_weight"] - first_control["post_weight"])
    return dict(status="passed", accounts=accounts, verified_control_identities=len(schedule),
                first_fill_target_minus_control_pp=first_difference)


def _drawdown(values, initial):
    peak = initial
    worst = 0.
    for value in values:
        peak = max(peak, value)
        worst = max(worst, 1 - value / peak)
    return worst


def _percentile(sorted_values, probability):
    rank = probability * (len(sorted_values) - 1)
    left = floor(rank)
    right = min(left + 1, len(sorted_values) - 1)
    return float(sorted_values[left] + (rank-left)*(sorted_values[right]-sorted_values[left]))


def verify_interval(paths, spec, primary):
    """Stream all draws day by day, preserve the cash identity, and check both endpoints."""
    full, target = paths["weekly20"], paths["target50"]
    years = spec["evaluation_years"]
    dates = [e["date"] for e in full]
    equal(dates, [e["date"] for e in target], "paired drawdown dates")
    if dates != sorted(set(dates)) or {int(d[:4]) for d in dates} != set(years):
        raise ValueError("Unexpected dates in drawdown interval")
    start = spec["initial_cash"]
    reserve = start / 2
    control_dd = _drawdown((reserve + .5*e["equity"] for e in full), start)
    target_dd = _drawdown((e["equity"] for e in target), start)
    difference = 100*(control_dd - target_dd)
    _fields(primary, {"difference_pp": difference}, "observed paired drawdown")

    settings = spec["uncertainty"]
    draws, block = settings["draws"], settings["block_sessions"]
    rng = np.random.Generator(np.random.PCG64(settings["seed"]))
    active = np.full(draws, float(start))
    dynamic = active.copy()
    control_peak = active.copy()
    target_peak = active.copy()
    control_worst = np.zeros(draws)
    target_worst = np.zeros(draws)
    for year in years:
        section = [i for i, day in enumerate(dates) if day.startswith(str(year))]
        n = len(section)
        factors = np.array([(1 + full[i]["daily_return"], 1 + target[i]["daily_return"])
                            for i in section])
        if not np.isfinite(factors).all() or np.any(factors <= 0):
            raise ValueError("Invalid daily wealth growth in drawdown interval")
        starts = rng.integers(0, n, size=(draws, (n+block-1)//block))
        for offset in range(n):
            ids = (starts[:, offset//block] + offset % block) % n
            active *= factors[ids, 0]
            dynamic *= factors[ids, 1]
            control = reserve + .5*active
            control_peak = np.maximum(control_peak, control)
            target_peak = np.maximum(target_peak, dynamic)
            control_worst = np.maximum(control_worst, 1 - control/control_peak)
            target_worst = np.maximum(target_worst, 1 - dynamic/target_peak)
    samples = np.sort(100*(control_worst - target_worst))
    expected = [_percentile(samples, p) for p in (.025, .975)]
    supplied = primary.get("interval95_pp")
    if not isinstance(supplied, (list, tuple)) or len(supplied) != 2:
        raise ValueError("Expected two interval95_pp endpoints")
    for actual, computed in zip(supplied, expected):
        if not isfinite(computed):
            raise ValueError("Undefined simulated drawdown")
        equal(actual, computed, "interval95_pp")
    return dict(status="passed", draws=draws, block_sessions=block, seed=settings["seed"],
                difference_pp=difference, interval95_pp=expected,
                fixed_reserve_preserved=True)
