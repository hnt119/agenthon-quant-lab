"""Verify the Sunday-close account directly against dated BTC/USD observations."""
from collections import defaultdict
from datetime import date, timedelta
from itertools import pairwise

from .cost_verify import _check_period, _fields, _position
from .verify import equal


def verify_weekly(rows, parent_spec, scenario, weekly_entries, period_summaries):
    """Replay from raw close and quote dates, independently of submitted signals and balances."""
    delay, fee_bps, slip_bps = parent_spec["scenarios"][scenario]
    if delay != 5:
        raise ValueError("Expected the frozen five-minute execution proxy")
    fee_rate = fee_bps / 10_000
    slip_rate = slip_bps / 10_000
    days = [date.fromisoformat(bar["date"]) for bar in rows]
    if any((b - a).days != 1 for a, b in pairwise(days)):
        raise ValueError("Cannot verify the schedule with noncontiguous UTC sessions")
    market = dict(zip(days, rows, strict=True))
    years = parent_spec["evaluation_years"]
    evaluation = [day for day in days if day.year in years]
    if not evaluation:
        raise ValueError("Missing weekly evaluation dates")

    cash = prior_equity = peak = parent_spec["initial_cash"]
    shares = 0.
    by_year = defaultdict(list)
    scheduled = []
    fills = 0
    for day, entry in zip(evaluation, weekly_entries, strict=True):
        bar = market[day]
        quote, close, minute = bar["price_5"], bar["close"], bar["minute_5"]
        if not 5 <= minute < 1440:
            raise ValueError(f"Ineligible UTC execution minute on {day}")
        signal_day = target = cutoff = None
        if day.isoweekday() == 1:
            sunday = day - timedelta(days=1)
            reference = sunday - timedelta(days=20)
            if reference not in market or sunday not in market:
                raise ValueError(f"Missing completed-close momentum history for {day}")
            target = int(market[sunday]["close"] / market[reference]["close"] - 1 > 0)
            signal_day = sunday.isoformat()
            cutoff = f"{day}T00:00:00Z"
            scheduled.append(day.isoformat())

        pretrade_equity = cash + shares * quote
        cash, shares, qty, price = _position(cash, shares, target, quote, fee_rate, slip_rate)
        proxy = f"{day}T{minute // 60:02d}:{minute % 60:02d}:00Z"
        if qty == 0 and entry.get("trade_quantity") != 0:
            raise ValueError(f"Unexpected trade_quantity on {day}")
        fill_value = abs(qty) * (price or 0.)
        equity = cash + shares * close
        peak = max(peak, equity)
        expected = dict(
            scenario=scenario, arm="weekly20", date=str(day),
            signal_session=signal_day, decision_time=cutoff, feature_cutoff=cutoff,
            execution_proxy_time=proxy, execution_time=proxy if qty else None,
            target_for_open=target, quote=quote, close=close, trade_quantity=qty, fill_price=price,
            fee=fee_rate * fill_value, slippage_cost=abs(qty) * quote * slip_rate,
            cash=cash, shares=shares, equity=equity, pnl=equity - prior_equity,
            daily_return=equity / prior_equity - 1, drawdown=1 - equity / peak,
            exposure=shares * close / equity, quoted_notional=abs(qty) * quote,
            turnover=abs(qty) * quote / pretrade_equity,
        )
        _fields(entry, expected, f"weekly {scenario} {day}")
        prior_equity = equity
        fills += int(qty != 0)
        by_year[str(day.year)].append(entry)

    year_keys = {str(y) for y in years}
    equal(set(by_year), year_keys, "weekly annual ledger coverage")
    equal(set(period_summaries), {"pooled"} | year_keys, "weekly summaries")
    opening = parent_spec["initial_cash"]
    _check_period(weekly_entries, opening, period_summaries["pooled"], "weekly pooled")
    for year, section in by_year.items():
        _check_period(section, opening, period_summaries[year], f"weekly {year}")
        opening = section[-1]["equity"]
    return dict(status="passed", scenario=scenario, portfolio_sessions=len(evaluation),
                scheduled_decisions=len(scheduled), first_scheduled_session=next(iter(scheduled), None),
                fills=fills, period_summaries=len(period_summaries))
