"""Independent direct Fourier transform and cash-flow reconstruction from source quotes."""
from decimal import Decimal as D
from math import cos, sin, pi, fsum, log, isclose
from statistics import median
from itertools import pairwise

N = 64
HANN = tuple((1 - cos(2 * pi * i / N)) / 2 for i in range(N))
BASIS = tuple(tuple(complex(cos(2 * pi * k * i / N), -sin(2 * pi * k * i / N)) for i in range(N)) for k in range(1, N//2 + 1))


def entropy(window):
    if min(window) == max(window):
        return None
    average = fsum(window) / N
    tapered = [(v - average) * w for v, w in zip(window, HANN, strict=True)]
    power = [abs(sum(z * v for z, v in zip(wave, tapered, strict=True)))**2 * (1 if k == N//2 else 2)
             for k, wave in enumerate(BASIS, 1)]
    mass = fsum(power)
    return -fsum((p / mass) * log(p / mass) for p in power if p) / log(N//2)


def near(a, b):
    if a is None or b is None:
        return a is b
    return isclose(float(a), float(b), rel_tol=2e-12, abs_tol=2e-11)


def check(name, errors, denominator):
    return {"name": name, "status": "failed" if errors else "passed",
            "failure_count": len(errors), "examples": errors[:5], "observations": denominator}


def verify(rows, spec, signals, fit, books, metrics):
    logs = [log(b["close"] / a["close"]) for a, b in pairwise(rows)]
    dates = [r["date"] for r in rows]
    es = [None if i < N else entropy(logs[i - N:i]) for i in range(len(rows))]
    cutoff = spec["partitions"]["train"][1]
    ids = [i for i, d in enumerate(dates) if d <= cutoff and es[i] is not None]
    mid = median(es[i] for i in ids)
    fit_ok = (fit["train_end"] == cutoff and [m["date"] for m in fit["members"]] == [dates[i] for i in ids]
              and all(near(m["entropy"], es[i]) for m, i in zip(fit["members"], ids)) and near(mid, fit["median"]))
    checks = [check("training_membership_and_threshold", [] if fit_ok else ["median or membership"], len(ids))]
    expected = []
    errors = []
    for i, (d, s) in enumerate(zip(dates, signals, strict=True)):
        momentum = D(str(rows[i]["close"])) / D(str(rows[i - 20]["close"])) - 1 if i >= 20 else None
        live = d >= cutoff
        on = live and momentum is not None and momentum > 0
        targets = {"buy_and_hold": int(live), "cash": 0, "momentum20": int(on),
                   "momentum20_fft": int(on and es[i] is not None and es[i] <= mid)}
        expected.append(targets)
        status = "warmup" if i < N else ("no_variation" if es[i] is None else "ok")
        if (d != s["date"] or not near(momentum, s["momentum20"]) or not near(es[i], s["entropy"])
                or s["entropy_status"] != status or s["targets"] != targets):
            errors.append(d)
    checks.append(check("independent_momentum_direct_dft_and_targets", errors, len(rows)))
    for arm in expected[0]:
        for treatment in ("gross", "net"):
            path = books[arm][treatment]
            fee = D(spec["frictions"]["net_fee_bps_each_fill"] if treatment == "net" else 0) / 10000
            h = D(spec["frictions"]["net_adverse_slippage_bps_each_fill"] if treatment == "net" else 0) / 10000
            cash = previous = peak = D(spec["initial_cash"])
            qty = D(0)
            errors, references = [], []
            for i, (r, line) in enumerate(zip(rows, path, strict=True)):
                op, cl = D(str(r["open"])), D(str(r["close"]))
                target = expected[i - 1][arm] if i else 0
                open_nav = cash + qty * op
                end_qty = qty
                if not target:
                    end_qty = D(0)
                elif not qty:
                    end_qty = cash / ((1 + fee) * op * (1 + h))
                u = end_qty - qty
                slip = abs(u) * op * h
                signed = u * op + slip
                commission = abs(signed) * fee
                cash = D(0) if u > 0 else cash - signed - commission
                nav = cash + end_qty * cl
                peak = max(peak, nav)
                wanted = {"trade_quantity": u, "fill_price": signed / u if u else None, "cash": cash, "shares": end_qty,
                          "equity": nav, "fee": commission, "slippage_cost": slip, "turnover": abs(u) * op / open_nav,
                          "pnl": nav - previous, "drawdown": 1 - nav / peak}
                if (line["date"] != r["date"] or line["target_for_open"] != target
                        or line["signal_date"] != (dates[i - 1] if u else None)
                        or any(not near(line[k], v) for k, v in wanted.items())):
                    errors.append(r["date"])
                references.append(wanted)
                previous, qty = nav, end_qty
            checks.append(check(f"{arm}.{treatment}.decimal_next_open_journal", errors, len(path)))
            errors = []
            for label, (a, b) in {"full": (dates[0], dates[-1]), **spec["partitions"]}.items():
                start, end = dates.index(a), dates.index(b)
                part = references[start:end + 1]
                initial = references[start - 1]["equity"] if start else D(spec["initial_cash"])
                peak, dd = initial, D(0)
                for item in part:
                    peak = max(peak, item["equity"])
                    dd = max(dd, 1 - item["equity"] / peak)
                wanted = {"total_return": part[-1]["equity"] / initial - 1, "max_drawdown": dd, "starting_equity": initial,
                          "ending_equity": part[-1]["equity"], "trade_events": sum(r["trade_quantity"] != 0 for r in part),
                          "turnover": sum(r["turnover"] for r in part), "fees": sum(r["fee"] for r in part),
                          "slippage_cost": sum(r["slippage_cost"] for r in part)}
                wanted["transaction_cost"] = wanted["fees"] + wanted["slippage_cost"]
                errors.extend(f"{label}.{k}" for k, v in wanted.items() if not near(metrics[arm][treatment][label][k], v))
            checks.append(check(f"{arm}.{treatment}.independent_periods", errors, 4))
    return checks
