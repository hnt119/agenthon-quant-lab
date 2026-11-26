"""Weekly BTC target and independently traded half-funded weekly sleeve."""
from .study import rebalance, require, timestamp


def _account(market, schedule, scenario, costs, initial_cash, arm, positive_target, reserve):
    _, fee_bps, slip_bps = costs
    fee_rate, slip_rate = fee_bps / 10_000, slip_bps / 10_000
    cash = initial_cash - reserve  # Spendable sleeve balance only.
    shares = 0.
    previous_equity = peak = initial_cash
    last_instruction = None
    ledger = []
    for bar, decision in zip(market, schedule, strict=True):
        day, quote, close = bar["date"], bar["price_5"], bar["close"]
        proxy = timestamp(day, bar["minute_5"])
        require((day, quote, close, proxy, scenario, "weekly20") ==
                tuple(decision[k] for k in ("date", "quote", "close", "execution_proxy_time", "scenario", "arm")),
                "Weekly schedule differs from allocation market or cost scenario")
        pretrade = reserve + cash + shares * quote
        signal = decision["target_for_open"]
        target = None
        quantity, fill, fee, slippage = 0., None, 0., 0.
        if signal is not None:
            require(signal in (0, 1), "Expected a binary instruction from the weekly controller")
            target = signal * positive_target
            instruction = (target, quote)
            # With no intervening cash flows, the same quote and instruction
            # already meet the last post-cost target, exactly in financial units.
            if instruction != last_instruction:
                cash, shares, quantity, fill, fee, slippage = rebalance(
                    cash, shares, target, quote, fee_rate, slip_rate)
            last_instruction = instruction

        total_cash = reserve + cash
        equity = total_cash + shares * close
        peak = max(peak, equity)
        quoted_notional = abs(quantity) * quote
        ledger.append(dict(
            date=day, arm=arm, scenario=scenario, cash=total_cash, shares=shares, equity=equity,
            signal_session=decision["signal_session"], feature_cutoff=decision["feature_cutoff"],
            decision_time=decision["decision_time"], target_for_open=target,
            execution_proxy_time=proxy, execution_time=proxy if quantity else None,
            quote=quote, close=close, trade_quantity=quantity, fill_price=fill, fee=fee,
            slippage_cost=slippage, turnover=quoted_notional / pretrade, quoted_notional=quoted_notional,
            exposure=shares * close / equity, pnl=equity - previous_equity,
            daily_return=equity / previous_equity - 1, drawdown=1 - equity / peak,
        ))
        previous_equity = equity
    return ledger


def allocation_entries(rows, full_weekly, scenario, costs, initial_cash=10000.):
    """Replay the verified weekly schedule against two separately funded accounts.

    For target50, target_for_open is the requested total-account BTC fraction
    at the execution quote after costs. For half_funded it is the active sleeve's
    0/1 instruction. Cash, equity, exposure, returns and turnover always describe
    the entire account, including any inactive reserve.
    """
    require(costs[0] == 5 and full_weekly, "Expected the frozen five-minute weekly schedule")
    first, last = full_weekly[0]["date"], full_weekly[-1]["date"]
    market = [bar for bar in rows if first <= bar["date"] <= last]
    target = _account(market, full_weekly, scenario, costs, initial_cash, "target50", .5, 0.)
    control = _account(market, full_weekly, scenario, costs, initial_cash, "half_funded", 1, initial_cash / 2)
    return target, control
