"""Locate observed sign changes on a finite cost path without assuming monotonicity."""
from itertools import pairwise
from math import isfinite


class RefinementBudgetReached(Exception):
    """The shared budget for additional simulated settings is fully reserved."""


def crossings(points, evaluate, *, zero_tolerance, width_tolerance, max_midpoints):
    """points contains all sorted (multiplier, difference) pairs for one criterion."""
    if len(points) < 2 or not all(isfinite(x) for x, _ in points):
        raise ValueError("A finite grid with at least two points is required")
    if not all(a[0] < b[0] for a, b in pairwise(points)):
        raise ValueError("The cost grid must increase strictly")

    def sign(value):
        if value is None:
            return None
        if not isfinite(value):
            raise ValueError("Use null for undefined statistics")
        return 0 if abs(value) <= zero_tolerance else (1 if value > 0 else -1)

    signs = [sign(y) for _, y in points]
    undefined = [x for (x, _), s in zip(points, signs) if s is None]
    flat = [[a, b] for (a, va), (b, vb) in pairwise(points)
            if va is not None and vb is not None and abs(va - vb) <= zero_tolerance]
    events = []
    i = 0
    while i < len(points):
        lo, vlo = points[i]
        if signs[i] == 0:
            start = i
            while i + 1 < len(points) and signs[i + 1] == 0:
                i += 1
            hi, vhi = points[i]
            events.append(dict(kind="sampled_equality" if i == start else "sampled_equal_range",
                               lo=lo, hi=hi, value_lo=vlo, value_hi=vhi,
                               estimate=lo if i == start else None,
                               boundary=start == 0 or i == len(points)-1))
        elif (i + 1 < len(points) and signs[i] in (-1, 1)
              and signs[i+1] == -signs[i]):
            hi, vhi = points[i+1]
            source_bracket = [lo, hi]
            trials = []
            kind = "bracketed"
            while hi - lo > width_tolerance:
                if len(trials) >= max_midpoints:
                    kind = "refinement_limit"
                    break
                mid = (lo + hi) / 2
                try:
                    value = evaluate(mid)
                except RefinementBudgetReached:
                    kind = "refinement_limit"
                    break
                trials.append([mid, value])
                direction = sign(value)
                if direction is None:
                    kind = "undefined_refinement"
                    break
                if direction == 0:
                    lo = hi = mid
                    vlo = vhi = value
                    kind = "sampled_equality"
                    break
                if direction == sign(vlo):
                    lo, vlo = mid, value
                else:
                    hi, vhi = mid, value
            estimate = (lo + hi) / 2 if kind in ("bracketed", "sampled_equality") else None
            events.append(dict(kind=kind, lo=lo, hi=hi, value_lo=vlo, value_hi=vhi, estimate=estimate,
                               source_bracket=source_bracket, trials=trials, boundary=False))
        i += 1
    unresolved = any(e["kind"] in ("undefined_refinement", "refinement_limit") for e in events)
    if unresolved or undefined:
        status = "incomplete"
    elif len(events) > 1:
        status = "multiple_detected"
    elif events:
        status = "crossing_detected" if events[0]["kind"] == "bracketed" else "sampled_equalities"
    else:
        status = "no_crossing_detected"
    return dict(status=status, events=events, undefined_samples=undefined, near_flat_intervals=flat)
