"""Paired total-wealth drawdowns and prespecified weekly allocation diagnostics."""
from datetime import date, timedelta
from itertools import pairwise
from math import ceil, fsum

import numpy as np

from .study import require


def primary_comparison(paths, summaries, spec):
    """Keep the inactive cash reserve fixed on each paired resampled path."""
    full, target = paths["weekly20"], paths["target50"]
    require([r["date"] for r in full] == [r["date"] for r in target], "Return dates differ")
    settings = spec["uncertainty"]
    draws, block = settings["draws"], settings["block_sessions"]
    rng = np.random.Generator(np.random.PCG64(settings["seed"]))
    initial, reserve = spec["initial_cash"], spec["inactive_cash"]
    active_fraction = (initial - reserve) / initial
    wealth = np.full((2, draws), initial, dtype=float)
    peak = wealth.copy()
    worst = np.zeros_like(wealth)
    for year in spec["evaluation_years"]:
        returns = np.array([[r["daily_return"] for r in path if int(r["date"][:4]) == year]
                            for path in (full, target)])
        n = returns.shape[1]
        require(n > 0, "Empty bootstrap year")
        starts = rng.integers(n, size=(draws, ceil(n / block)))
        # All replicates use the frozen RNG order. Process small batches to bound memory.
        for first in range(0, draws, 128):
            batch = slice(first, min(draws, first + 128))
            indices = ((starts[batch, :, None] + np.arange(block)) % n).reshape(len(starts[batch]), -1)[:, :n]
            values = wealth[:, batch, None] * np.cumprod(1 + returns[:, indices], axis=2)
            wealth[:, batch] = values[:, :, -1]
            values[0] = reserve + active_fraction * values[0]
            peaks = np.maximum(peak[:, batch, None], np.maximum.accumulate(values, axis=2))
            worst[:, batch] = np.maximum(worst[:, batch], (1 - values / peaks).max(axis=2))
            peak[:, batch] = peaks[:, :, -1]
    deltas = 100 * (worst[0] - worst[1])
    require(np.isfinite(deltas).all(), "Nonfinite paired drawdown")
    difference = summaries["half_funded"]["pooled"]["max_drawdown"] - summaries["target50"]["pooled"]["max_drawdown"]
    return {"difference_pp": 100 * difference,
            "interval95_pp": np.quantile(deltas, [0.025, 0.975], method="linear").tolist()}


def _worst_decline(path, initial):
    opening = str(date.fromisoformat(path[0]["date"]) - timedelta(days=1))
    peak, peak_date, peak_exposure = initial, opening, 0.
    worst = None
    for row in path:
        if row["equity"] >= peak:
            peak, peak_date, peak_exposure = row["equity"], row["date"], row["exposure"]
        loss = 1 - row["equity"] / peak
        if worst is None or loss > worst["drawdown"]:
            worst = dict(peak_date=peak_date, trough_date=row["date"], drawdown=loss,
                         peak_exposure=peak_exposure, trough_exposure=row["exposure"])
    return worst


def diagnostics(paths, initial):
    target, sizing = paths["target50"], paths["half_funded"]
    first_fill = [next(row for row in path if row["trade_quantity"]) for path in (target, sizing)]
    require(first_fill[0]["date"] == first_fill[1]["date"], "First fills differ")
    weights = []
    for row in first_fill:
        held = row["shares"] * row["quote"]
        weights.append(held / (held + row["cash"]))
    decisions = [row for row in target if row["decision_time"] is not None]
    consecutive = [b for a, b in pairwise(decisions) if a["target_for_open"] == b["target_for_open"] == 0.5]
    buys = sum(row["trade_quantity"] > 0 for row in consecutive)
    sells = sum(row["trade_quantity"] < 0 for row in consecutive)
    return dict(first_fill=dict(date=first_fill[0]["date"], target50_weight=weights[0],
                                half_funded_weight=weights[1], difference_pp=100 * (weights[0] - weights[1])),
                unchanged_positive=dict(decisions=len(consecutive), fills=buys+sells, buys=buys, sells=sells,
                                        turnover=fsum(row["turnover"] for row in consecutive),
                                        fees_usd=fsum(row["fee"] for row in consecutive),
                                        slippage_usd=fsum(row["slippage_cost"] for row in consecutive)),
                worst_declines={arm: _worst_decline(path, initial) for arm, path in paths.items()})
