"""Causal descriptive spectra for completed, session-indexed log returns.

The historical workflow can publish these descriptive profiles after portfolio
evaluation. The window ends at the completed close for each observation.
Callers own session validation, corporate actions, and availability timestamps.
The fixed 64-observation window is part of the proposed experiment contract.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Iterable

from scipy.fft import rfft

WINDOW = 64
MAX_OBSERVATIONS = 10_000
METHOD_ID = "causal-return-spectrum-v1"


def _values(values: Iterable[float], limit: int) -> list[float]:
    if isinstance(values, (str, bytes)):
        raise ValueError("Supply finite real log returns, not text")
    result = []
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise ValueError("Supply an iterable of finite real log returns") from exc
    for value in iterator:
        if len(result) >= limit:
            raise ValueError(f"At most {limit} observations are allowed")
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError("Each log return must be a finite real number")
        try:
            number = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Each log return must be finite in float64") from exc
        if not math.isfinite(number):
            raise ValueError("Missing or nonfinite log returns are unsupported")
        result.append(number)
    return result


def spectral_profile(completed_log_returns: Iterable[float]) -> dict:
    """Profile exactly 64 completed log returns; never pad or fill.

    Demean inside this window, apply a periodic Hann taper, then use rFFT.
    Exclude DC. Double interior positive-frequency power, but not Nyquist.
    Normalize retained power to sum to one; divide Shannon entropy by log(32).
    Frequencies are cycles per trading observation, not cycles per calendar day.
    Period is descriptive, not a forecast. Constant windows have null metrics.
    Rescaling before centering and FFT protects against overflow; only relative
    powers are returned, so this is not an absolute spectral-density estimate.
    """
    values = _values(completed_log_returns, WINDOW)
    if len(values) != WINDOW:
        raise ValueError(f"Exactly {WINDOW} completed log returns are required")
    frequencies = [k / WINDOW for k in range(1, WINDOW // 2 + 1)]
    result = {
        "schema_version": 1,
        "method_id": METHOD_ID,
        "window_observations": WINDOW,
        "window_function": "periodic_hann",
        "demean": True,
        "dc_excluded": True,
        "frequency_cycles_per_observation": frequencies,
        "status": "no_variation",
        "spectral_entropy": None,
        "dominant_period_observations": None,
        "power_fraction": None,
    }
    scale = max(abs(value) for value in values)
    if scale == 0:
        return result
    normalized = [value / scale for value in values]
    mean = math.fsum(normalized) / WINDOW
    centered = [value - mean for value in normalized]
    deviation = max(abs(value) for value in centered)
    if deviation == 0:
        return result
    tapered = [
        (value / deviation) * (0.5 - 0.5 * math.cos(2 * math.pi * j / WINDOW))
        for j, value in enumerate(centered)
    ]
    spectrum = rfft(tapered, workers=1)
    power = [
        (1.0 if k == WINDOW // 2 else 2.0) * float(abs(spectrum[k]) ** 2)
        for k in range(1, WINDOW // 2 + 1)
    ]
    total = math.fsum(power)
    if not math.isfinite(total) or total <= 0:
        raise ArithmeticError("Unexpected nonpositive or nonfinite spectral energy")
    fractions = [value / total for value in power]
    entropy = -math.fsum(p * math.log(p) for p in fractions if p > 0) / math.log(len(fractions))
    # Bound representational roundoff only; the formula lies in [0, 1].
    if entropy < -1e-12 or entropy > 1 + 1e-12:
        raise ArithmeticError("Normalized spectral entropy is outside its range")
    peak_index = max(range(len(fractions)), key=fractions.__getitem__)
    result.update(
        status="ok",
        spectral_entropy=min(1.0, max(0.0, entropy)),
        dominant_period_observations=1.0 / frequencies[peak_index],
        power_fraction=fractions,
    )
    return result


def rolling_spectral_profiles(completed_log_returns: Iterable[float]) -> list[dict | None]:
    """Align each profile to its last input; the first 63 outputs are None.

    Each available profile reads only values[i-63:i+1]. No centered windows,
    global normalization, threshold fitting, or future values are used. At most
    10,000 observations are accepted. Invalid data fails rather than being filled.
    """
    values = _values(completed_log_returns, MAX_OBSERVATIONS)
    return [
        None if i < WINDOW - 1 else spectral_profile(values[i - WINDOW + 1:i + 1])
        for i in range(len(values))
    ]


def _log_return(previous: float, current: float) -> float:
    # log1p preserves small moves. Extreme finite prices can overflow a ratio.
    ratio = current / previous
    if 0.5 <= ratio <= 2.0:
        return math.log1p((current - previous) / previous)
    if 0 < ratio < math.inf and ratio >= 2.0 ** -1022:
        return math.log(ratio)
    return math.log(current) - math.log(previous)


def historical_profiles(rows: list[dict], quality: dict) -> dict:
    """Attach return-window endpoints to the observed, normalized session dates."""
    returns = [_log_return(before["close"], after["close"]) for before, after in zip(rows, rows[1:])]
    # The first close has no preceding return. Keep it as an observation.
    profiles = [None, *rolling_spectral_profiles(returns)]
    observations = []
    for row, profile in zip(rows, profiles, strict=True):
        observations.append({
            "date": row["date"],
            "status": profile["status"] if profile else "warmup",
            "spectral_entropy": profile["spectral_entropy"] if profile else None,
            "dominant_period_observations": profile["dominant_period_observations"] if profile else None,
            "power_fraction": profile["power_fraction"] if profile else None,
        })
    return {
        "schema_version": 1, "method_id": METHOD_ID, "window_returns": WINDOW,
        "available_at": "after the final observed session close in each trailing window",
        "return_basis": "close-to-close log price return, excluding cash distributions",
        "price_adjustment": quality["price_adjustment"], "source": quality["source"],
        "input_sha256": quality["input_sha256"],
        "timestamp_convention": quality["timestamp_convention"], "session_timezone": quality["session_timezone"],
        "units": {"spectral_entropy": "dimensionless, normalized to [0,1]",
                  "dominant_period_observations": "trading observations",
                  "power_fraction": "fraction of retained positive-frequency power"},
        "frequency_cycles_per_observation": [k / WINDOW for k in range(1, WINDOW // 2 + 1)],
        "observations": observations,
    }
