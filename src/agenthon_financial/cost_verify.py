"""Independent accounting checks for the fixed BTC transaction-cost path."""
from collections import defaultdict
from math import fsum, isfinite, prod, sqrt

from .verify import equal


def _fields(actual, expected, context):
    for key, value in expected.items():
        if key not in actual:
            raise ValueError(f"Missing {context} {key}")
        observed = actual[key]
        if isinstance(value, (float, int)):
            if type(observed) not in (float, int) or not isfinite(observed):
                raise ValueError(f"Invalid {context} {key}: {observed!r}")
        equal(observed, value, f"{context} {key}")


def _position(cash, shares, target, quote, fee, slip):
    """Solve for the *post-cost equity* implied by the specified target.

    At the quote, BTC is worth H before and wE after the fill. The signed
    traded notional is wE-H. Each quoted dollar bought or sold moves cash by
    a side-specific factor k, so E = cash + kH + (1-k)wE.
    """
    held_value = shares * quote
    if target is None:
        return cash, shares, 0.0, None
    imbalance = target * cash - (1 - target) * held_value
    if imbalance == 0:
        return cash, shares, 0.0, None
    side = 1 if imbalance > 0 else -1
    factor = (1 + side * slip) * (1 + side * fee)
    equity = (cash + factor * held_value) / (1 + (factor - 1) * target)
    new_shares = target * equity / quote
    return (1 - target) * equity, new_shares, new_shares - shares, quote * (1 + side * slip)


def _check_period(section, start, metrics, name):
    returns = [row["daily_return"] for row in section]
    count = len(returns)
    avg = fsum(returns) / count
    sd = sqrt(fsum((v - avg) ** 2 for v in returns) / (count - 1))
    growth = prod(1 + v for v in returns)
    high = start
    worst = 0.
    for row in section:
        high = max(high, row["equity"])
        worst = max(worst, 1 - row["equity"] / high)
    fees = fsum(r["fee"] for r in section)
    slippage = fsum(r["slippage_cost"] for r in section)
    _fields(metrics, dict(
        starting_equity=start, ending_equity=start * growth, pnl=start * (growth - 1),
        total_return=growth - 1, annual_return=growth ** (365 / count) - 1,
        annual_vol=sd * sqrt(365), sharpe=avg * sqrt(365) / sd if sd else None,
        max_drawdown=worst, trade_events=sum(r["trade_quantity"] != 0 for r in section),
        fees=fees, slippage_cost=slippage, transaction_cost=fees + slippage,
        turnover=fsum(r["turnover"] for r in section),
        quoted_traded_notional=fsum(r["quoted_notional"] for r in section),
        mean_close_exposure=fsum(r["exposure"] for r in section) / count,
        sessions_in_market_fraction=sum(r["shares"] > 0 for r in section) / count,
        ending_cash=section[-1]["cash"], ending_shares=section[-1]["shares"], observations=count,
    ), name)


def verify_cost_books(rows, observations, weights, spec, entries, portfolios, multiplier):
    """Replay positions from admitted quotes and independently qualified prior signals.

    No reported quantity, cash balance, or fill price drives the next reconstructed
    position. Verification uses the original financial verifier's numeric tolerance.
    """
    paths = defaultdict(list)
    scenarios = set()
    for entry in entries:
        paths[entry["arm"]].append(entry)
        scenarios.add(entry["scenario"])
    equal(len(scenarios), 1, "one scenario per cost setting")
    equal(set(paths), set(spec["arms"]), "ledger arm coverage")
    equal(set(portfolios), set(paths), "summary arm coverage")
    years = {str(y) for y in spec["evaluation_years"]}
    indices = [i for i, row in enumerate(rows) if row["date"][:4] in years]
    if not indices or indices[0] == 0:
        raise ValueError("Missing evaluation dates or preceding session")
    annual_weights = {str(year): record["weight"] for year, record in weights.items()}
    fee, slip = 50 * multiplier / 10_000, 10 * multiplier / 10_000
    fills = 0
    for arm, path in paths.items():
        cash = prior = peak = spec["initial_cash"]
        shares = 0.
        by_year = defaultdict(list)
        for index, row in zip(indices, path, strict=True):
            market = rows[index]
            day = market["date"]
            year = day[:4]
            if arm == "passive_mix":
                target = annual_weights[year] if day.endswith("-01-01") else None
            else:
                target = observations[index - 1]["targets"][arm]
            quote, close = market["price_5"], market["close"]
            pretrade = cash + shares * quote
            cash, shares, quantity, price = _position(cash, shares, target, quote, fee, slip)
            charge = abs(quantity) * (price or 0) * fee
            drag = abs(quantity) * quote * slip
            equity = cash + shares * close
            peak = max(peak, equity)
            minute = market["minute_5"]
            cutoff = day + "T00:00:00Z"
            proxy = f"{day}T{minute // 60:02d}:{minute % 60:02d}:00Z"
            _fields(row, dict(
                date=day, quote=quote, close=close, signal_session=rows[index - 1]["date"],
                feature_cutoff=cutoff, decision_time=cutoff, execution_proxy_time=proxy,
                execution_time=proxy if quantity else None, target_for_open=target,
                trade_quantity=quantity, fill_price=price, fee=charge, slippage_cost=drag,
                cash=cash, shares=shares, equity=equity, pnl=equity - prior,
                daily_return=equity / prior - 1, drawdown=1 - equity / peak,
                turnover=abs(quantity) * quote / pretrade, quoted_notional=abs(quantity) * quote,
                exposure=shares * close / equity,
            ), f"{arm} {day}")
            by_year[year].append(row)
            fills += int(quantity != 0)
            prior = equity
        equal(set(by_year), years, "annual ledger coverage")
        equal(set(portfolios[arm]), years | {"pooled"}, "annual summary coverage")
        start = spec["initial_cash"]
        _check_period(path, start, portfolios[arm]["pooled"], f"{arm} pooled")
        for year, section in by_year.items():
            _check_period(section, start, portfolios[arm][year], f"{arm} {year}")
            start = section[-1]["equity"]
    return dict(status="passed", portfolio_sessions=len(indices) * len(paths),
                period_summaries=(len(years) + 1) * len(paths), fills=fills)
