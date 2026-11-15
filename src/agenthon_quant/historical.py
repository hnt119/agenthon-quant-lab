"""Continuous, single-asset portfolios evaluated over three chronological periods."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from . import trading


STRATEGIES = ("sma", "buy_and_hold", "cash")
SPEC_KEYS = {
    "workflow", "data", "source", "synthetic", "price_adjustment",
    "timestamp_convention", "session_timezone", "columns", "initial_cash",
    "fee_bps", "slippage_bps", "lookback", "train_end", "validation_end", "strategies",
}


def _parameters(spec: dict, dates: list[str]) -> tuple[dict, dict[str, tuple[int, int]]]:
    if not isinstance(spec, dict) or spec.get("workflow") != "historical":
        raise ValueError("workflow must be 'historical'")
    unsupported = set(spec) - SPEC_KEYS
    if unsupported:
        raise ValueError(f"Unsupported historical specification fields: {', '.join(sorted(unsupported))}")
    if not isinstance(spec.get("data"), str) or not spec["data"].strip():
        raise ValueError("data must identify the input file")
    config = trading.portfolio_parameters(spec, len(dates))
    strategies = config.get("strategies", list(STRATEGIES))
    if (not isinstance(strategies, list) or not strategies
            or any(name not in STRATEGIES for name in strategies)
            or len(strategies) != len(set(strategies))):
        raise ValueError("strategies must be a nonempty list of distinct names from sma, buy_and_hold, cash")
    config["requested_strategies"] = list(strategies)
    config["strategies"] = list(strategies)
    if "buy_and_hold" not in strategies:
        config["strategies"].append("buy_and_hold")
    train_end, validation_end = config.get("train_end"), config.get("validation_end")
    if train_end not in dates or validation_end not in dates:
        raise ValueError("train_end and validation_end must be observed session dates")
    # Bounds are half-open. The second and third books inherit the prior close.
    train_stop, validation_stop = dates.index(train_end) + 1, dates.index(validation_end) + 1
    if not config["lookback"] < train_stop < validation_stop < len(dates):
        raise ValueError("Train needs one post-warmup observation and validation and test must be nonempty and ordered")
    return config, {"train": (0, train_stop), "validation": (train_stop, validation_stop),
                    "test": (validation_stop, len(dates))}


def _targets(name: str, rows: list[dict], lookback: int) -> list[int]:
    if name == "sma":
        return trading.signals(rows, lookback)
    if name == "buy_and_hold":
        return [int(i >= lookback - 1) for i in range(len(rows))]
    return [0] * len(rows)


def _summarize(ledger: list[dict], initial_cash: float, intervals: dict[str, tuple[int, int]]) -> dict:
    equity = [row["equity"] for row in ledger]
    peak = initial_cash
    drawdown = []
    for value in equity:
        peak = max(peak, value)
        drawdown.append(1 - value / peak)
    periods = {}
    for period, (start, stop) in intervals.items():
        starting_equity = equity[start - 1] if start else initial_cash
        periods[period] = {"start": ledger[start]["date"], "end": ledger[stop - 1]["date"],
                           **trading.period_metrics(ledger[start:stop], starting_equity)}
    return {"metrics": trading.period_metrics(ledger, initial_cash), "periods": periods,
            "equity": equity, "drawdown": drawdown}


def _period_check(summary: dict, ledger: list[dict], initial_cash: float,
                  intervals: dict[str, tuple[int, int]]) -> dict:
    """Cross-check the reported periods against per-session accounting and path."""
    errors = []
    previous = initial_cash
    for period, (start, stop) in intervals.items():
        section = ledger[start:stop]
        metrics = summary["periods"][period]
        pnl = math.fsum(row["pnl"] for row in section)
        # Tie cash P&L to endpoints. Compare at the portfolio's operation scale
        # when nearly equal large equities have been subtracted.
        scale = max(abs(previous), abs(section[-1]["equity"]))
        if (not trading._near(metrics["pnl"], pnl, operation_scale=scale)
                or not trading._near(metrics["starting_equity"], previous)
                or not trading._near(metrics["ending_equity"], section[-1]["equity"])
                or not trading._near(metrics["total_return"], pnl / previous)
                or metrics["observations"] != stop - start):
            errors.append(period)
        previous = section[-1]["equity"]
    metrics = summary["metrics"]
    if not trading._near(metrics["max_drawdown"], max(summary["drawdown"])):
        errors.append("full drawdown")
    for metric in ("fees", "slippage_cost", "transaction_cost", "turnover", "trade_events"):
        if not trading._near(metrics[metric], math.fsum(p[metric] for p in summary["periods"].values())):
            errors.append(metric)
    return {"name": "period_accounting", "status": "failed" if errors else "passed",
            "details": errors or "Period opening equities, P&L, returns, counts and costs reconcile to the continuous book."}


def _benchmark_check(name: str, equity: list[float], rows: list[dict], initial_cash: float,
                     lookback: int, fee_bps: float, slippage_bps: float) -> dict:
    """Independent closed-form path for either the flat or single-entry strategy."""
    if name == "cash":
        expected = [initial_cash] * len(rows)
    else:
        # First execution is observation lookback (zero-based). The purchased
        # quantity is fixed thereafter, so a separate ledger is unnecessary.
        entry_open = rows[lookback]["open"]
        units = initial_cash / (entry_open * (1 + slippage_bps / 10000) * (1 + fee_bps / 10000))
        expected = [initial_cash] * lookback + [units * row["close"] for row in rows[lookback:]]
    failed = sum(not trading._near(value, reference) for value, reference in zip(equity, expected))
    return {"name": "benchmark_reference_path", "status": "failed" if failed else "passed",
            "details": f"Compared {len(equity)} marked equities to the independent {name} path",
            "failure_count": failed}


def evaluate(spec: dict, rows: list[dict], quality: dict) -> dict[str, Any]:
    """Account on normalized daily rows; the public file entry point is run()."""
    dates = [row["date"] for row in rows]
    config, intervals = _parameters(spec, dates)
    initial_cash, lookback = config["initial_cash"], config["lookback"]
    portfolios, checks = {}, []
    try:
        for name in config["strategies"]:
            targets = _targets(name, rows, lookback)
            portfolios[name] = {}
            for treatment in ("gross", "net"):
                fee, slippage = (0.0, 0.0) if treatment == "gross" else (config["fee_bps"], config["slippage_bps"])
                ledger = trading.simulate_ledger(rows, targets, initial_cash, fee, slippage)
                summary = _summarize(ledger, initial_cash, intervals)
                verified = trading.verify_ledger(ledger, rows, initial_cash, fee, slippage, lookback, name)
                verified.append(_period_check(summary, ledger, initial_cash, intervals))
                if name != "sma":
                    verified.append(_benchmark_check(name, summary["equity"], rows, initial_cash, lookback, fee, slippage))
                checks.extend({**check, "name": f"{name}.{treatment}.{check['name']}"} for check in verified)
                portfolios[name][treatment] = summary
                del ledger
    except ArithmeticError as exc:
        raise ValueError("Historical portfolio arithmetic exceeded the supported range; rescale prices and cash") from exc

    checks.append({"name": "market_source_and_corporate_actions", "status": "unavailable",
                   "details": "Source, corporate-action treatment and exchange-calendar completeness are user declarations."})
    warnings = ["Using test-period outcomes to change the strategy compromises the holdout.",
                "Execution assumes fractional, liquid positions and the declared costs. Dividends, interest, taxes and market impact are excluded."]
    if config.get("synthetic"):
        warnings.insert(0, "Synthetic session prices demonstrate portfolio mechanics.")
    return {
        "workflow": "historical", "results": {"quality": quality, "dates": dates, "strategies": portfolios},
        "checks": checks, "warnings": warnings, "assumptions": {
            **config,
            "signal": "Long when the completed close exceeds its trailing simple mean. Flat during warmup and on equality.",
            "execution": "Apply the prior close target at the next observed open. Mark remaining shares at the final close.",
            "benchmarks": "Buy and hold is included for every selection and enters after the same warmup. Cash remains uninvested and earns zero.",
            "sizing": "Invest all available cash in fractional shares, including the buy fee. Close the position on a flat target.",
            "costs": "Fees apply to filled notional, and adverse slippage applies to the quoted open on both sides.",
            "periods": "Carry shares and cash through train, validation and test. Each period starts from previous close equity.",
            "drawdown": "Daily path uses the running full-period peak. Each period summary resets its peak to opening equity.",
            "selection": "All parameters and portfolios are fixed by the supplied specification before calculation.",
            "metric_units": "Returns, drawdowns and exposure are fractions. Turnover sums quoted traded notional divided by pre-trade equity.",
        },
    }


def run(spec: dict, data_path: Path) -> dict[str, Any]:
    from .market_data import read_market_data

    rows, quality = read_market_data(data_path, spec)
    return evaluate(spec, rows, quality)
