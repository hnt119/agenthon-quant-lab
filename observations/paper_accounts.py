"""Two hypothetical weekly accounts. The recorder owns timestamps and durable ordering."""
from datetime import date, timedelta
from math import isfinite

from agenthon_financial.cost_verify import _fields, _position
from agenthon_financial.study import rebalance, require
from agenthon_financial.verify import equal

INITIAL = 10_000.0
FEE = 50 / 10_000
SLIP = 10 / 10_000
# Each entry gives the fixed reserve and the positive target of the spendable sleeve.
ARMS = {"target50": (0.0, 0.5), "half_funded": (5_000.0, 1.0)}


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def _price(value):
    require(_number(value) and value > 0, "Expected a finite positive BTC/USD price")
    return value


def _date(value):
    day = date.fromisoformat(value)
    require(day.isoformat() == value, "Expected an ISO UTC session date")
    return day


def decision(monday_iso, closes):
    """Accept exactly 21 chronological UTC daily closes, ending on the prior Sunday."""
    monday = _date(monday_iso)
    require(monday.weekday() == 0 and len(closes) == 21, "Expected Monday and 21 completed closes")
    for i, row in enumerate(closes):
        require(_date(row["date"]) == monday - timedelta(days=21-i), "Unexpected signal session")
        _price(row["close"])
    momentum = closes[-1]["close"] / closes[0]["close"] - 1
    require(isfinite(momentum), "Non-finite momentum")
    positive = momentum > 0
    return dict(momentum20=momentum, positive=positive, signal_date=closes[-1]["date"],
                reference_date=closes[0]["date"], target50=0.5 if positive else 0.0,
                half_funded_sleeve=float(positive))


def fresh_accounts():
    """Cash includes the inactive reserve; no interest, transfers, leverage or initial BTC."""
    return {arm: dict(cash=INITIAL, shares=0., reserve=reserve, fees=0., slippage=0.,
                      fill_count=0, first_fill_weight=None, last_target=None, last_quote=None)
            for arm, (reserve, _) in ARMS.items()}


def _check_accounts(accounts):
    require(isinstance(accounts, dict) and accounts.keys() == ARMS.keys(), "Expected both accounts")
    for arm, (reserve, positive_target) in ARMS.items():
        row = accounts[arm]
        for key in ("cash", "shares", "reserve", "fees", "slippage"):
            require(_number(row[key]) and row[key] >= 0, f"Invalid {arm} {key}")
        require(row["reserve"] == reserve and row["cash"] >= reserve, "Inactive reserve differs")
        count, weight = row["fill_count"], row["first_fill_weight"]
        require(type(count) is int and count >= 0, "Invalid fill count")
        require(weight is None if count == 0 else _number(weight) and 0 < weight <= 1,
                "Invalid first-fill weight")
        if count == 0:
            require(row["cash"] == INITIAL and all(row[k] == 0 for k in ("shares", "fees", "slippage")),
                    "Balances changed without a fill")
        if row["last_target"] is None:
            require(row["last_quote"] is None and count == 0, "Missing prior instruction")
        else:
            require(_number(row["last_target"]) and row["last_target"] in (0., positive_target),
                    "Invalid prior target")
            _price(row["last_quote"])


def apply_fill(before, positive, quote):
    """Apply only a committed eligible instruction to a later accepted paper quote."""
    _check_accounts(before)
    _price(quote)
    require(type(positive) is bool, "Expected a frozen boolean signal")
    after, trades = {}, {}
    for arm, (reserve, positive_target) in ARMS.items():
        prior = before[arm]
        target = positive_target if positive else 0.
        cash, shares = prior["cash"] - reserve, prior["shares"]
        quantity, fill_price, fee, drag = 0., None, 0., 0.
        if (target, quote) != (prior["last_target"], prior["last_quote"]):
            cash, shares, quantity, fill_price, fee, drag = rebalance(cash, shares, target, quote, FEE, SLIP)
        total_cash = cash + reserve
        weight = shares * quote / (total_cash + shares * quote)
        first = weight if quantity and prior["fill_count"] == 0 else prior["first_fill_weight"]
        after[arm] = dict(cash=total_cash, shares=shares, reserve=reserve,
                          fees=prior["fees"] + fee, slippage=prior["slippage"] + drag,
                          fill_count=prior["fill_count"] + int(quantity != 0), first_fill_weight=first,
                          last_target=target, last_quote=quote)
        trades[arm] = dict(quantity=quantity, fill_price=fill_price, fee=fee, slippage=drag,
                           post_quote_weight=weight)
    verify_fill(before, positive, quote, after, trades)
    return after, trades


def verify_fill(before, positive, quote, after, trades):
    """Replay the post-cost equity equation and cash movements from prior balances."""
    _check_accounts(before)
    _check_accounts(after)
    _price(quote)
    require(type(positive) is bool and trades.keys() == ARMS.keys(), "Invalid fill record")
    for arm, (reserve, positive_target) in ARMS.items():
        prior = before[arm]
        target = positive_target if positive else 0.
        instruction = None if (prior["last_target"], prior["last_quote"]) == (target, quote) else target
        cash, shares, quantity, fill = _position(prior["cash"] - reserve, prior["shares"],
                                                  instruction, quote, FEE, SLIP)
        fee = abs(quantity) * fill * FEE if fill is not None else 0.
        drag = abs(quantity) * quote * SLIP
        equity = cash + reserve + shares * quote
        weight = shares * quote / equity
        first = weight if quantity and prior["fill_count"] == 0 else prior["first_fill_weight"]
        _fields(after[arm], dict(cash=cash + reserve, shares=shares, fees=prior["fees"] + fee,
                                slippage=prior["slippage"] + drag, last_quote=quote, last_target=target,
                                fill_count=prior["fill_count"] + int(quantity != 0), first_fill_weight=first),
                arm)
        entry = trades[arm]
        _fields(entry, dict(quantity=quantity, fill_price=fill, fee=fee, slippage=drag,
                            post_quote_weight=weight), arm)
        signed_cash_flow = entry["quantity"] * (entry["fill_price"] or 0.) + entry["fee"]
        equal(after[arm]["cash"], prior["cash"] - signed_cash_flow, arm + " cash flow")
        equal(equity, prior["cash"] + prior["shares"] * quote - fee - drag, arm + " equity conservation")


def mark_accounts(accounts, price):
    """Value total wealth at the UTC session close; this operation changes no holdings."""
    _check_accounts(accounts)
    _price(price)
    return {arm: _price(row["cash"] + row["shares"] * price) for arm, row in accounts.items()}


def summarize(accounts, marks, start, end):
    """Use calendar-date close marks; a gap or pending close withholds the primary endpoint."""
    _check_accounts(accounts)
    first, last = _date(start), _date(end)
    n = (last - first).days + 1
    require(1 <= n <= 364, "Expected a bounded close period of at most 52 weeks")
    days = [(first + timedelta(days=i)).isoformat() for i in range(n)]
    require(set(marks).issubset(days), "Mark outside observation window")
    latest_attempt = max(marks, default=None)
    latest_valid = None
    peaks = dict.fromkeys(ARMS, INITIAL)
    max_dd = dict.fromkeys(ARMS, 0.)
    observed = 0
    missing = 0
    for day in days:
        values = marks.get(day)
        if values is None:
            missing += int(latest_attempt is not None and day <= latest_attempt)
            continue
        require(isinstance(values, dict) and values.keys() == ARMS.keys(), "Invalid closing mark")
        latest_valid = day
        observed += 1
        for arm, value in values.items():
            _price(value)
            peaks[arm] = max(peaks[arm], value)
            max_dd[arm] = max(max_dd[arm], 1 - value / peaks[arm])
    complete = observed == n
    status = "complete" if complete else "incomplete" if missing else "collecting"
    account_summary = {arm: dict(ending_wealth=marks[end][arm] if marks.get(end) else None,
                                 latest_observed_wealth=marks[latest_valid][arm] if latest_valid else None,
                                 max_drawdown=max_dd[arm] if complete else None,
                                 fees=row["fees"], slippage=row["slippage"], fill_count=row["fill_count"],
                                 first_fill_weight=row["first_fill_weight"])
                       for arm, row in accounts.items()}
    return dict(status=status, observed_marks=observed, missing_marks=missing,
                pending_marks=n-observed-missing, latest_mark=latest_valid, accounts=account_summary,
                primary_drawdown_difference_pp=100 * (max_dd["half_funded"] - max_dd["target50"])
                if complete else None)
