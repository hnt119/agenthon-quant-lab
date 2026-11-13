"""Scalar European Black–Scholes–Merton valuation and independent checks.

The scalar price/Greek formulas adapt the dataset-independent conventions in
Agenthon R29 agent/quant/pricing.py (MIT, Agenthon Team 166 contributors).
No competition dispatch, fixtures, numerical answers, or evaluator code is used.
"""
from __future__ import annotations

import math
from typing import Any

from scipy.integrate import quad

_NUMERIC = ("spot", "strike", "maturity_years", "volatility", "rate", "dividend_yield")
_ALLOWED = {*_NUMERIC, "workflow", "currency", "option_type", "volatility_scenarios"}
_GREEKS = ("delta", "gamma", "vega", "rho", "theta")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number, expressed in documented units")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} is outside floating-point range") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def validate_spec(spec: dict) -> dict:
    """Reject unsupported conventions instead of guessing rate or time units."""
    if not isinstance(spec, dict):
        raise ValueError("option specification must be an object")
    unknown = set(spec) - _ALLOWED
    if unknown:
        raise ValueError("unsupported option fields: " + ", ".join(sorted(unknown)))
    if spec.get("workflow") != "options":
        raise ValueError("workflow must be options")
    missing = set(_NUMERIC) | {"currency"}
    missing -= set(spec)
    if missing:
        raise ValueError("missing explicit option inputs: " + ", ".join(sorted(missing)))
    p = {name: _number(spec[name], name) for name in _NUMERIC}
    if p["spot"] <= 0 or p["strike"] <= 0:
        raise ValueError("spot and strike must be strictly positive")
    if p["maturity_years"] < 0 or p["volatility"] < 0:
        raise ValueError("maturity_years and volatility must be nonnegative")
    currency = spec["currency"]
    if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
        raise ValueError("currency must be an explicit three-letter uppercase label")
    kind = spec.get("option_type", "both")
    if kind not in ("call", "put", "both"):
        raise ValueError("option_type must be call, put, or both")
    scenarios = spec.get("volatility_scenarios", [])
    if not isinstance(scenarios, list) or len(scenarios) > 100:
        raise ValueError("volatility_scenarios must be a list of at most 100 decimal volatilities")
    scenarios = [_number(v, "scenario volatility") for v in scenarios]
    if any(v < 0 for v in scenarios):
        raise ValueError("scenario volatilities must be nonnegative")
    return {**p, "workflow": "options", "currency": currency, "option_type": kind,
            "volatility_scenarios": scenarios}


def _cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _terms(p: dict) -> tuple[float, float, float, float]:
    S, K, T, v, r, q = (p[k] for k in _NUMERIC)
    try:
        discount_q = math.exp(-q * T)
        stock, strike, sd = S * discount_q, K * math.exp(-r * T), v * math.sqrt(T)
    except OverflowError as exc:
        raise ValueError("discount factors exceed supported floating-point range") from exc
    if not all(math.isfinite(x) and x > 0 for x in (stock, strike, discount_q)) or not math.isfinite(sd):
        raise ValueError("discounted inputs overflow or underflow floating-point range")
    if v > 0 and T > 0 and sd == 0:
        raise ValueError("total volatility underflows floating-point range")
    return stock, strike, discount_q, sd


def _value(p: dict, kind: str) -> dict:
    S, K, T, v, r, q = (p[k] for k in _NUMERIC)
    stock, strike, discount_q, sd = _terms(p)
    sign = 1 if kind == "call" else -1
    if T == 0 or v == 0:
        spread = stock - strike
        price = max(sign * spread, 0.0)
        kink = spread == 0.0
        itm = sign * spread > 0.0
        # At T=0 the price no longer depends on r or sigma. Calendar theta is
        # deliberately withheld: a derivative through expiry is not defined.
        greeks = {
            "delta": None if kink else (sign * discount_q if itm else 0.0),
            "gamma": None if kink else 0.0,
            "vega": 0.0 if T == 0 or not kink else None,
            "rho": 0.0 if T == 0 else (None if kink else (sign * T * strike if itm else 0.0)),
            "theta": None if T == 0 or kink else (sign * (q * stock - r * strike) if itm else 0.0),
        }
        if not all(x is None or math.isfinite(x) for x in (price, *greeks.values())):
            raise ValueError("boundary price or Greeks exceed floating-point range")
        return {"price": price, "greeks": greeks}
    d1 = (math.log(S) - math.log(K) + (r - q) * T) / sd + sd / 2
    d2 = d1 - sd
    if not all(math.isfinite(x) for x in (d1, d2)):
        raise ValueError("standardized option inputs exceed floating-point range")
    density = math.exp(-d1 * d1 / 2) / math.sqrt(2 * math.pi)
    if S * sd == 0:
        raise ValueError("gamma denominator underflows floating-point range")
    price = sign * (stock * _cdf(sign * d1) - strike * _cdf(sign * d2))
    # Only remove tiny negative cancellation noise; verification sees the raw
    # mathematical price otherwise and checks the discounted bounds.
    if -1e-13 * max(stock, strike) <= price < 0:
        price = 0.0
    greeks = {
        "delta": sign * discount_q * _cdf(sign * d1),
        "gamma": discount_q * density / (S * sd),
        "vega": stock * density * math.sqrt(T),
        "rho": sign * T * strike * _cdf(sign * d2),
        "theta": -stock * density * v / (2 * math.sqrt(T)) - sign * r * strike * _cdf(sign * d2) + sign * q * stock * _cdf(sign * d1),
    }
    if not all(math.isfinite(x) for x in (price, *greeks.values())):
        raise ValueError("price or Greeks exceed floating-point range")
    return {"price": price, "greeks": greeks}


def _check(name: str, ok: bool, details: str, **extra: Any) -> dict:
    return {"name": name, "status": "passed" if ok else "failed", "details": details, **extra}


def _quadrature(p: dict, kind: str) -> tuple[float, float]:
    """Integrate discounted terminal payoff against its risk-neutral density.

    Algebra combines exp(log S_T) with the Gaussian density to avoid overflow.
    Independent QUADPACK integration, not a second call to the analytic pricer.
    The interval contains both density centres plus ten standard deviations.
    """
    stock, strike, _, sd = _terms(p)
    S, K, T, v, r, q = (p[k] for k in _NUMERIC)
    if T == 0 or v == 0:
        payoff = max((stock - strike) * (1 if kind == "call" else -1), 0.0)
        return payoff, 0.0
    zstrike = (math.log(K) - math.log(S) - (r - q - v * v / 2) * T) / sd
    lower, upper = -10.0, sd + 10.0
    if kind == "call":
        lower = max(lower, zstrike)
    else:
        upper = min(upper, zstrike)
    tail_bound = (stock + strike) * _cdf(-10.0)
    if lower >= upper:
        return 0.0, tail_bound
    scale = max(stock, strike)
    sign = 1 if kind == "call" else -1
    def payoff_density(z: float) -> float:
        return sign * ((stock / scale) * math.exp(-0.5 * (z - sd) ** 2)
                       - (strike / scale) * math.exp(-0.5 * z ** 2)) / math.sqrt(2 * math.pi)
    points = [z for z in (0.0, sd) if lower < z < upper]
    integral = quad(payoff_density, lower, upper, points=points, epsabs=1e-11,
                    epsrel=1e-11, limit=150, full_output=1)
    if len(integral) != 3:
        raise ArithmeticError("QUADPACK did not report convergence")
    value, error = integral[:2]
    return value * scale, error * scale + tail_bound


def _finite_difference(p: dict, kind: str, greek: str, h: float) -> float:
    field = {"delta": "spot", "gamma": "spot", "vega": "volatility",
             "rho": "rate", "theta": "maturity_years"}[greek]
    up, down = dict(p), dict(p)
    up[field], down[field] = p[field] + h, p[field] - h
    plus, minus = _value(up, kind)["price"], _value(down, kind)["price"]
    if greek == "gamma":
        return (plus - 2 * _value(p, kind)["price"] + minus) / h ** 2
    result = (plus - minus) / (2 * h)
    return -result if greek == "theta" else result


def verify(spec: dict, results: dict) -> list[dict]:
    """Validate supplied results; callers can detect corrupted saved prices/Greeks.

    A result may contain a single requested side. Parity then uses an independently
    computed complementary side, which is labelled in the check.
    """
    p = validate_spec(spec)
    stock, strike, _, sd = _terms(p)
    requested = ("call", "put") if p["option_type"] == "both" else (p["option_type"],)
    checks: list[dict] = []
    sides = results.get("valuations", {}) if isinstance(results, dict) else {}
    if not isinstance(sides, dict):
        checks.append(_check("valuation_structure", False, "valuations must be an object keyed by option side"))
        sides = {}
    for kind in requested:
        side = sides.get(kind)
        good = isinstance(side, dict) and isinstance(side.get("greeks"), dict)
        if good:
            value = side.get("price")
            good = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            good = good and set(side["greeks"]) == set(_GREEKS)
            good = good and all(x is None or (isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)) for x in side["greeks"].values())
        checks.append(_check(f"{kind}_finite_structure", good, "Finite price and exactly five finite-or-null Greek quantities required"))
        if not good:
            continue
        value = float(side["price"])
        low, high = (max(stock - strike, 0), stock) if kind == "call" else (max(strike - stock, 0), strike)
        tolerance = 2e-10 * max(1.0, stock, strike)
        checks.append(_check(f"{kind}_price_bounds", low - tolerance <= value <= high + tolerance,
                             "Discounted European lower and upper bounds", lower=low, upper=high, observed=value, tolerance=tolerance))
        if sd <= 12:
            try:
                reference, error = _quadrature(p, kind)
                if not all(math.isfinite(x) for x in (reference, error)):
                    raise ArithmeticError("Nonfinite integration result")
                tolerance = 2e-8 * max(1.0, stock, strike) + error
                checks.append(_check(f"{kind}_payoff_quadrature", abs(value - reference) <= tolerance,
                                     "Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary",
                                     reference=reference, observed=value, absolute_error=abs(value-reference), tolerance=tolerance,
                                     integration_error_estimate_plus_tail_bound=error))
            except (ArithmeticError, ValueError) as exc:
                checks.append({"name": f"{kind}_payoff_quadrature", "status": "unavailable", "details": str(exc)})
        else:
            checks.append({"name": f"{kind}_payoff_quadrature", "status": "unavailable",
                           "details": "Independent quadrature supported only for sigma*sqrt(T) <= 12"})
        if p["maturity_years"] == 0 or p["volatility"] == 0:
            checks.append({"name": f"{kind}_greek_finite_differences", "status": "unavailable",
                           "details": "Central finite differences are not used at the expiry or zero-volatility boundary; null quantities are explicitly unavailable"})
            expected = _value(p, kind)["greeks"]
            checks.append(_check(f"{kind}_boundary_greeks", side["greeks"] == expected,
                                 "Check explicit deterministic derivatives and unavailable boundary quantities"))
            continue
        steps = {"delta": p["spot"] * min(1e-3, sd * 1e-2), "gamma": p["spot"] * min(1e-3, sd * 1e-2),
                 "vega": min(1e-4, p["volatility"] * 1e-2), "rho": 1e-5,
                 "theta": min(1e-4, p["maturity_years"] * 1e-2)}
        for greek, h in steps.items():
            field = {"delta": "spot", "gamma": "spot", "vega": "volatility", "rho": "rate", "theta": "maturity_years"}[greek]
            if h <= 8 * math.ulp(p[field]):
                checks.append({"name": f"{kind}_{greek}_finite_difference", "status": "unavailable", "details": "Perturbation is not representable reliably in float64"})
                continue
            try:
                coarse, fine = _finite_difference(p, kind, greek, h), _finite_difference(p, kind, greek, h / 2)
                if not all(math.isfinite(x) for x in (coarse, fine)):
                    raise ArithmeticError("Nonfinite finite-difference estimate")
            except (ArithmeticError, ValueError) as exc:
                checks.append({"name": f"{kind}_{greek}_finite_difference", "status": "unavailable", "details": str(exc)})
                continue
            estimate = side["greeks"][greek]
            tolerance = (2e-6 if greek == "gamma" else 2e-5) + 5e-4 * abs(fine)
            stable = abs(coarse - fine) <= tolerance
            agrees = estimate is not None and abs(estimate - fine) <= tolerance
            checks.append(_check(f"{kind}_{greek}_finite_difference", stable and agrees,
                                 "Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative",
                                 observed=estimate, coarse=coarse, fine=fine, step=h, tolerance=tolerance,
                                 step_convergence_passed=stable))
    valid_prices = all(isinstance(sides.get(k), dict) and isinstance(sides[k].get("price"), (int, float)) and not isinstance(sides[k]["price"], bool) and math.isfinite(sides[k]["price"]) for k in requested)
    if valid_prices:
        call = sides["call"]["price"] if "call" in requested else _value(p, "call")["price"]
        put = sides["put"]["price"] if "put" in requested else _value(p, "put")["price"]
        residual = call - put - (stock - strike)
        tolerance = 2e-10 * max(1.0, stock, strike)
        checks.append(_check("put_call_parity", abs(residual) <= tolerance,
                             "C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested",
                             residual=residual, tolerance=tolerance))
    else:
        checks.append({"name": "put_call_parity", "status": "unavailable", "details": "Requested prices have invalid structure"})
    expected_scenarios = p["volatility_scenarios"]
    scenarios = results.get("volatility_scenarios", []) if isinstance(results, dict) else []
    if expected_scenarios or scenarios:
        valid = isinstance(scenarios, list) and len(scenarios) == len(expected_scenarios)
        checks.append(_check("scenario_roster", valid, "Scenario outputs must match the complete requested volatility list and order"))
        if valid:
            for i, (volatility, scenario) in enumerate(zip(expected_scenarios, scenarios)):
                matches = isinstance(scenario, dict) and scenario.get("volatility") == volatility
                checks.append(_check(f"scenario[{i}].input", matches, "Scenario volatility equals requested decimal volatility"))
                if matches:
                    scenario_spec = {**p, "volatility": volatility, "volatility_scenarios": []}
                    checks.extend({**check, "name": f"scenario[{i}].{check['name']}"} for check in verify(scenario_spec, scenario))
    return checks


def run(spec: dict) -> dict:
    p = validate_spec(spec)
    kinds = ("call", "put") if p["option_type"] == "both" else (p["option_type"],)
    results = {"valuations": {kind: _value(p, kind) for kind in kinds}, "volatility_scenarios": []}
    for volatility in p["volatility_scenarios"]:
        scenario_spec = {**p, "volatility": volatility, "volatility_scenarios": []}
        scenario = {"volatility": volatility, "valuations": {kind: _value(scenario_spec, kind) for kind in kinds}}
        scenario["checks"] = verify(scenario_spec, scenario)
        results["volatility_scenarios"].append(scenario)
    checks = verify(p, results)
    warnings = ["Model values are conditional on constant volatility, rates and continuous dividend yield; numerical checks do not establish market accuracy."]
    if p["maturity_years"] == 0:
        warnings.append("At expiry the payoff is exact; calendar theta is unavailable and delta/gamma are undefined at the strike.")
    if p["volatility"] == 0 or 0 in p["volatility_scenarios"]:
        warnings.append("Zero-volatility prices use the deterministic discounted payoff. At its kink, non-two-sided derivatives are null; finite-difference Greek checks are unavailable.")
    if any(c["status"] == "unavailable" for c in checks):
        warnings.append("Some validation checks are unavailable; inspect their applicability before interpreting results.")
    return {"workflow": "options", "results": results, "checks": checks, "warnings": warnings,
            "assumptions": {"model": "Black-Scholes-Merton; European vanilla; one unit of underlying",
                            "currency": p["currency"], "rate_compounding": "continuous",
                            "dividends": "constant continuous annual yield; discrete dividends unsupported",
                            "maturity": "explicit year fraction; no calendar/day-count conversion performed",
                            "volatility": "annualized log-return volatility in decimal units",
                            "greek_units": {"delta": "price per one currency-unit increase in spot", "gamma": "delta per one currency-unit increase in spot",
                                            "vega": "price per +1.0 decimal annual volatility (multiply by 0.01 for one percentage point)",
                                            "rho": "price per +1.0 decimal annual rate (multiply by 0.01 for one percentage point)",
                                            "theta": "calendar theta: -dPrice/dMaturity, per year"},
                            "random_seed": None}}
