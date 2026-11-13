#!/usr/bin/env python3
"""Rebuild the authored demonstration fixture; no market observations are used."""

from datetime import date, timedelta
import csv
import math
from pathlib import Path
import random


SEED = 20261114


def generate(destination: Path) -> list[str]:
    rng = random.Random(SEED)
    dates = []
    current = date(2025, 1, 2)
    previous_close = 100.0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["date", "open", "close"])
        for index in range(180):
            while current.weekday() >= 5:
                current += timedelta(days=1)
            drift = 0.0015 if index < 60 else (-0.0005 if index < 120 else -0.0008)
            opening = previous_close * (1 + (rng.random() - 0.5) * 0.008)
            closing = opening * (1 + drift + 0.011 * math.sin(index * 0.57) + (rng.random() - 0.5) * 0.012)
            writer.writerow([current.isoformat(), f"{opening:.6f}", f"{closing:.6f}"])
            dates.append(current.isoformat())
            previous_close = closing
            current += timedelta(days=1)
    return dates


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "examples" / "data" / "synthetic_prices.csv"
    dates = generate(destination)
    print(f"Wrote {len(dates)} synthetic rows, seed={SEED}, to {destination}")
    print(f"Development ends {dates[119]}; holdout starts {dates[120]}")
