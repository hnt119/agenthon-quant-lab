"""Deterministic, single-asset SMA research with an auditable cash ledger.

No orders, downloads, optimization, or model calls are performed here. Signals
use completed closes; changes in position execute at the following row's open.
"""

from __future__ import annotations

import csv
from datetime import date
import math
from pathlib import Path
from typing import Any


SPEC_KEYS = {
    "workflow", "data", "source", "price_adjustment", "timestamp_convention",
    "initial_cash", "fee_bps", "slippage_bps", "lookback", "development_end",
    "holdout_start", "synthetic",
}
MAX_ROWS = 10_000
MAX_BYTES = 100_000_000
ABS_TOL = 1e-7
REL_TOL = 1e-10
ROUNDING_ULPS = 8


def _number(value: Any, name: str, minimum: float = 0.0, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number) or (number <= minimum if positive else number < minimum):
        comparison = ">" if positive else ">="
        raise ValueError(f"{name} must be finite and {comparison} {minimum}")
    return number


def _date(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a YYYY-MM-DD session date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a YYYY-MM-DD session date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be a YYYY-MM-DD session date")
    return value


def load_prices(path: Path) -> list[dict[str, Any]]:
    """Read CSV or optional PyArrow Parquet; reject silent sorting/coercion."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Price input does not exist: {path}")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"Price input exceeds the {MAX_BYTES}-byte limit")
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("CSV requires a unique header")
            if not {"date", "open", "close"}.issubset(reader.fieldnames):
                raise ValueError("Price data requires date, open, and close columns")
            raw = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("CSV has a row with the wrong number of columns")
                raw.append(row)
                if len(raw) > MAX_ROWS:
                    raise ValueError(f"Price input exceeds the {MAX_ROWS}-row limit")
    elif path.suffix.lower() in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise ValueError("Parquet reader unavailable: install agenthon-quant-lab[parquet] (PyArrow)") from exc
        parquet = pq.ParquetFile(path)
        if parquet.metadata.num_rows > MAX_ROWS:
            raise ValueError(f"Price input exceeds the {MAX_ROWS}-row limit")
        if not {"date", "open", "close"}.issubset(parquet.schema_arrow.names):
            raise ValueError("Price data requires date, open, and close columns")
        raw = parquet.read(columns=["date", "open", "close"]).to_pylist()
    else:
        raise ValueError("Price input must be .csv, .parquet, or .pq")
    if not raw:
        raise ValueError("Price input contains no observations")
    cleaned = []
    previous = ""
    for index, row in enumerate(raw):
        raw_date = row["date"]
        if isinstance(raw_date, date) and not hasattr(raw_date, "hour"):
            raw_date = raw_date.isoformat()
        session = _date(raw_date, f"row {index + 1} date")
        if session <= previous:
            raise ValueError("Dates must be unique and strictly increasing; input is never silently sorted")
        cleaned_row = {"date": session}
        for name in ("open", "close"):
            try:
                raw_value = row[name]
                if isinstance(raw_value, bool):
                    raise ValueError("boolean price")
                value = float(raw_value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"row {index + 1} {name} must be numeric") from exc
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"row {index + 1} {name} must be positive and finite")
            cleaned_row[name] = value
        cleaned.append(cleaned_row)
        previous = session
    return cleaned


def validate_spec(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ValueError("Trading specification must be an object")
    unknown = set(spec) - SPEC_KEYS
    if unknown:
        raise ValueError(f"Unsupported trading specification keys: {', '.join(sorted(unknown))}")
    if spec.get("workflow") != "trading":
        raise ValueError("workflow must be 'trading'")
    if not isinstance(spec.get("data"), str) or not spec["data"].strip():
        raise ValueError("data must identify the input file")
    if not isinstance(spec.get("source"), str) or not spec["source"].strip():
        raise ValueError("source must describe where the observations came from")
    if spec.get("price_adjustment") not in {"unadjusted", "split_adjusted"}:
        raise ValueError("price_adjustment must be 'unadjusted' or 'split_adjusted'; dividend total-return series are unsupported")
    if spec.get("timestamp_convention") != "session_date":
        raise ValueError("timestamp_convention must be 'session_date'; intraday/timezone timestamps are unsupported")
    config = dict(spec)
    config["initial_cash"] = _number(spec.get("initial_cash", 10000.0), "initial_cash", positive=True)
    for name in ("fee_bps", "slippage_bps"):
        config[name] = _number(spec.get(name, 0.0), name)
        if config[name] >= 10000:
            raise ValueError(f"{name} must be below 10000 basis points")
    lookback = spec.get("lookback", 20)
    if isinstance(lookback, bool) or not isinstance(lookback, int) or not 2 <= lookback <= 10000:
        raise ValueError("lookback must be an integer from 2 to 10000, chosen before evaluation")
    if len(rows) < lookback + 2:
        raise ValueError("Price data needs at least lookback + 2 observations")
    config["lookback"] = lookback
    if not isinstance(spec.get("synthetic", False), bool):
        raise ValueError("synthetic must be a boolean")
    config["synthetic"] = spec.get("synthetic", False)
    development_end = _date(spec.get("development_end"), "development_end")
    holdout_start = _date(spec.get("holdout_start"), "holdout_start")
    dates = [row["date"] for row in rows]
    if development_end not in dates or holdout_start not in dates:
        raise ValueError("development_end and holdout_start must be observed session dates")
    split = dates.index(holdout_start)
    if split != dates.index(development_end) + 1:
        raise ValueError("holdout_start must be the next observation after development_end")
    if split <= lookback or split >= len(rows):
        raise ValueError("Development must include a post-warmup observation and holdout must be nonempty")
    return config


def signals(rows: list[dict[str, Any]], lookback: int) -> list[int]:
    """Target at each completed close; equality to the moving average is flat."""
    output = []
    for index, row in enumerate(rows):
        if index + 1 < lookback:
            output.append(0)
        else:
            average = math.fsum(x["close"] for x in rows[index - lookback + 1:index + 1]) / lookback
            output.append(int(row["close"] > average))
    return output


def _roundoff(*values: float) -> float:
    """Small float64 allowance at the scale of a financial operation.

    Cancellation to zero does not erase the precision of the original notional.
    This is an eight-ULP bound, not a percentage of the portfolio value.
    """
    scale = max((abs(value) for value in values), default=0.0)
    if not math.isfinite(scale):
        raise ValueError("Trading arithmetic exceeded the finite numeric range; rescale input prices and cash")
    return ROUNDING_ULPS * math.ulp(scale)


def _simulate(rows: list[dict[str, Any]], targets: list[int], initial_cash: float,
              fee_bps: float, slippage_bps: float) -> list[dict[str, Any]]:
    fee_rate, slip_rate = fee_bps / 10000, slippage_bps / 10000
    cash, shares, previous_equity = initial_cash, 0.0, initial_cash
    ledger = []
    for index, row in enumerate(rows):
        opening, closing = row["open"], row["close"]
        target = targets[index - 1] if index else 0
        before_cash, before_shares = cash, shares
        pre_trade_equity = cash + shares * opening
        quantity, fill, fee = 0.0, None, 0.0
        if target == 1 and shares == 0:
            fill = opening * (1 + slip_rate)
            quantity = cash / (fill * (1 + fee_rate))
            fee = quantity * fill * fee_rate
            shares = quantity
            cash -= quantity * fill + fee
            # Algebraically an all-cash buy has zero residual. Clamp only a few
            # representable rounding units at the original operation scale.
            if abs(cash) <= _roundoff(before_cash, quantity * fill, fee):
                cash = 0.0
        elif target == 0 and shares > 0:
            fill = opening * (1 - slip_rate)
            quantity = -shares
            fee = abs(quantity) * fill * fee_rate
            cash += abs(quantity) * fill - fee
            shares = 0.0
        slippage_cost = 0.0 if fill is None else abs(quantity) * abs(fill - opening)
        equity = cash + shares * closing
        previous_close = rows[index - 1]["close"] if index else opening
        entry = {
            "date": row["date"], "open": opening, "close": closing,
            "target_at_close": targets[index], "target_for_open": target,
            "signal_date": rows[index - 1]["date"] if index and quantity else None,
            "cash_before": before_cash, "shares_before": before_shares,
            "trade_quantity": quantity, "fill_price": fill,
            "fee": fee, "slippage_cost": slippage_cost,
            "quoted_notional": abs(quantity) * opening,
            "turnover": abs(quantity) * opening / pre_trade_equity,
            "cash": cash, "shares": shares, "equity": equity,
            "pnl": equity - previous_equity,
            "overnight_pnl": before_shares * (opening - previous_close),
            "intraday_pnl": shares * (closing - opening),
            "exposure": shares * closing / equity,
        }
        if any(isinstance(value, (int, float)) and not math.isfinite(value) for value in entry.values()):
            raise ValueError("Trading arithmetic exceeded the finite numeric range; rescale input prices and cash")
        ledger.append(entry)
        previous_equity = equity
    return ledger


def _near(a: float, b: float, *, operation_scale: float = 0.0) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL,
                        abs_tol=max(ABS_TOL, _roundoff(operation_scale)))


def verify_ledger(ledger: list[dict[str, Any]], rows: list[dict[str, Any]], initial_cash: float,
                  fee_bps: float = 0.0, slippage_bps: float = 0.0,
                  lookback: int = 20, strategy: str = "sma") -> list[dict[str, Any]]:
    """Reconcile reported balances against raw prices and prior balances.

    This verifier does not call the simulator. Its failures never rewrite a
    reported trade or balance. It also independently recomputes signal timing.
    """
    failures: dict[str, list[str]] = {
        "ledger_shape_and_quotes": [], "signal_and_execution_timing": [],
        "cash_shares_equity_reconciliation": [], "fee_slippage_reconciliation": [],
        "pnl_reconciliation": [], "long_only_cash_constraints": [],
    }
    if not isinstance(ledger, list):
        return [{"name": "ledger_shape_and_quotes", "status": "failed",
                 "details": ["Ledger must be a list of records"], "failure_count": 1}]
    if len(ledger) != len(rows):
        failures["ledger_shape_and_quotes"].append("Ledger length does not match input length")
    cash, shares, equity, expected_previous_target = initial_cash, 0.0, initial_cash, 0
    for index, (entry, quote) in enumerate(zip(ledger, rows)):
        location = f"row {index + 1}"
        if not isinstance(entry, dict):
            failures["ledger_shape_and_quotes"].append(location + ": entry must be an object")
            continue
        try:
            for value in entry.values():
                if isinstance(value, bool) or (isinstance(value, (int, float)) and not math.isfinite(value)):
                    raise ValueError("nonfinite ledger value")
            opening, closing = quote["open"], quote["close"]
            quantity, fill = entry["trade_quantity"], entry["fill_price"]
            if entry["date"] != quote["date"] or not _near(entry["open"], opening) or not _near(entry["close"], closing):
                failures["ledger_shape_and_quotes"].append(location)
            if strategy == "buy_and_hold":
                expected_close_target = int(index >= lookback - 1)
            elif strategy == "sma":
                history = [x["close"] for x in rows[max(0, index + 1 - lookback):index + 1]]
                expected_close_target = int(len(history) == lookback and closing > math.fsum(history) / lookback)
            else:
                raise ValueError("unknown verification strategy")
            valid_trade = (quantity > 0 and shares == 0 and expected_previous_target == 1) or (
                quantity < 0 and shares > 0 and expected_previous_target == 0) or (
                quantity == 0 and expected_previous_target == int(shares > 0))
            expected_signal_date = rows[index - 1]["date"] if index and quantity else None
            if (entry["target_at_close"] != expected_close_target
                    or entry["target_for_open"] != expected_previous_target
                    or entry["signal_date"] != expected_signal_date or not valid_trade):
                failures["signal_and_execution_timing"].append(location)
            if quantity:
                expected_fill = opening * (1 + (1 if quantity > 0 else -1) * slippage_bps / 10000)
                expected_fee = abs(quantity) * expected_fill * fee_bps / 10000
                expected_slip = abs(quantity) * abs(expected_fill - opening)
                if fill is None or not _near(fill, expected_fill):
                    failures["fee_slippage_reconciliation"].append(location + " fill")
            else:
                expected_fill, expected_fee, expected_slip = 0.0, 0.0, 0.0
                if fill is not None:
                    failures["fee_slippage_reconciliation"].append(location + " unexpected fill")
            if not _near(entry["fee"], expected_fee) or not _near(entry["slippage_cost"], expected_slip):
                failures["fee_slippage_reconciliation"].append(location + " costs")
            next_cash = math.fsum((cash, -quantity * expected_fill, -expected_fee))
            cash_scale = max(abs(cash), abs(quantity * expected_fill), expected_fee)
            cash_tolerance = max(ABS_TOL, _roundoff(cash_scale))
            next_shares = shares + quantity
            next_equity = next_cash + next_shares * closing
            if (not _near(entry["cash_before"], cash, operation_scale=cash_scale)
                    or not _near(entry["cash"], next_cash, operation_scale=cash_scale)
                    or any(not _near(a, b) for a, b in (
                (entry["shares_before"], shares), (entry["shares"], next_shares),
                (entry["equity"], next_equity),
                (entry["quoted_notional"], abs(quantity) * opening),
                (entry["turnover"], abs(quantity) * opening / (cash + shares * opening)),
                (entry["exposure"], next_shares * closing / next_equity),
            ))):
                failures["cash_shares_equity_reconciliation"].append(location)
            prior_close = rows[index - 1]["close"] if index else opening
            overnight = shares * (opening - prior_close)
            intraday = next_shares * (closing - opening)
            decomposed_pnl = overnight + intraday - expected_fee - expected_slip
            pnl_scale = max(abs(equity), abs(next_equity), abs(overnight), abs(intraday), expected_fee, expected_slip)
            if any(not _near(a, b, operation_scale=pnl_scale) for a, b in (
                (entry["pnl"], next_equity - equity), (entry["pnl"], decomposed_pnl),
                (entry["overnight_pnl"], overnight), (entry["intraday_pnl"], intraday),
            )):
                failures["pnl_reconciliation"].append(location)
            if (next_cash < -cash_tolerance or next_shares < -ABS_TOL or next_equity <= 0
                    or (expected_previous_target == 1 and abs(next_cash) > cash_tolerance)
                    or (expected_previous_target == 0 and abs(next_shares) > ABS_TOL)):
                failures["long_only_cash_constraints"].append(location)
            # A verified all-in purchase has mathematically zero cash. Reset
            # only the verifier's reconstructed roundoff residue; never modify
            # the supplied ledger or absorb a material balance discrepancy.
            if quantity > 0 and abs(next_cash) <= _roundoff(cash_scale):
                next_cash = 0.0
            cash, shares, equity = next_cash, next_shares, next_equity
            expected_previous_target = expected_close_target
        except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            failures["ledger_shape_and_quotes"].append(f"{location}: {type(exc).__name__}")
    return [{
        "name": name, "status": "failed" if errors else "passed",
        "details": errors[:20] if errors else "All observations reconciled",
        "failure_count": len(errors), "absolute_tolerance": ABS_TOL, "relative_tolerance": REL_TOL,
        "cash_and_pnl_roundoff_ulps": ROUNDING_ULPS,
    } for name, errors in failures.items()]


def _metrics(ledger: list[dict[str, Any]], starting_equity: float) -> dict[str, Any]:
    peak, max_drawdown = starting_equity, 0.0
    for row in ledger:
        peak = max(peak, row["equity"])
        max_drawdown = max(max_drawdown, 1 - row["equity"] / peak)
    metrics = {
        "starting_equity": starting_equity, "ending_equity": ledger[-1]["equity"],
        "total_return": ledger[-1]["equity"] / starting_equity - 1,
        "pnl": ledger[-1]["equity"] - starting_equity,
        "max_drawdown": max_drawdown,
        "mean_close_exposure": math.fsum(row["exposure"] for row in ledger) / len(ledger),
        "sessions_in_market_fraction": sum(row["shares"] > 0 for row in ledger) / len(ledger),
        "turnover": math.fsum(row["turnover"] for row in ledger),
        "quoted_traded_notional": math.fsum(row["quoted_notional"] for row in ledger),
        "fees": math.fsum(row["fee"] for row in ledger),
        "slippage_cost": math.fsum(row["slippage_cost"] for row in ledger),
        "transaction_cost": math.fsum(row["fee"] + row["slippage_cost"] for row in ledger),
        "trade_events": sum(row["trade_quantity"] != 0 for row in ledger),
        "ending_cash": ledger[-1]["cash"], "ending_shares": ledger[-1]["shares"],
        "observations": len(ledger),
    }
    if any(not math.isfinite(value) for value in metrics.values()):
        raise ValueError("Trading summary metrics exceeded the finite numeric range; rescale input prices and cash")
    return metrics


def _account(rows: list[dict[str, Any]], targets: list[int], config: dict[str, Any],
             fee_bps: float, slippage_bps: float) -> dict[str, Any]:
    try:
        ledger = _simulate(rows, targets, config["initial_cash"], fee_bps, slippage_bps)
    except ArithmeticError as exc:
        raise ValueError("Trading arithmetic exceeded the supported numeric range; rescale input prices and cash") from exc
    split = next(i for i, row in enumerate(rows) if row["date"] == config["holdout_start"])
    return {
        "metrics": _metrics(ledger, config["initial_cash"]),
        "periods": {
            "development": {"start": rows[0]["date"], "end": config["development_end"],
                            **_metrics(ledger[:split], config["initial_cash"])},
            "holdout": {"start": config["holdout_start"], "end": rows[-1]["date"],
                        **_metrics(ledger[split:], ledger[split - 1]["equity"])},
        },
        "ledger": ledger,
        "trades": [{"date": row["date"], "signal_date": row["signal_date"],
                    "side": "BUY" if row["trade_quantity"] > 0 else "SELL",
                    "quantity": abs(row["trade_quantity"]), "fill_price": row["fill_price"],
                    "fee": row["fee"], "slippage_cost": row["slippage_cost"]}
                   for row in ledger if row["trade_quantity"]],
    }


def run(spec: dict[str, Any], data_path: Path) -> dict[str, Any]:
    rows = load_prices(Path(data_path))
    config = validate_spec(spec, rows)
    try:
        targets = signals(rows, config["lookback"])
    except ArithmeticError as exc:
        raise ValueError("Moving average arithmetic exceeded the supported numeric range; rescale input prices") from exc
    benchmark_targets = [int(index >= config["lookback"] - 1) for index in range(len(rows))]
    results: dict[str, Any] = {}
    checks = []
    for name, selected_targets in (("strategy", targets), ("buy_and_hold", benchmark_targets)):
        result = {
            "gross": _account(rows, selected_targets, config, 0, 0),
            "net": _account(rows, selected_targets, config, config["fee_bps"], config["slippage_bps"]),
        }
        results[name] = result
        for treatment in ("gross", "net"):
            fees = config["fee_bps"] if treatment == "net" else 0
            slip = config["slippage_bps"] if treatment == "net" else 0
            for check in verify_ledger(result[treatment]["ledger"], rows, config["initial_cash"], fees, slip,
                                       config["lookback"], "sma" if name == "strategy" else "buy_and_hold"):
                checks.append({**check, "name": f"{name}.{treatment}.{check['name']}"})
    checks.append({"name": "input_source_and_adjustments_independently_verified", "status": "unavailable",
                   "details": "Source, completeness, tradability, and corporate-action treatment are user declarations; no data vendor verification was performed."})
    warnings = [
        "Historical or synthetic simulation does not establish predictive accuracy or trading profitability.",
        "No dividends, interest on cash, taxes, market impact, liquidity constraints, or minimum lot sizes are modeled.",
        "Open and close prices must use the same adjustment basis. Unadjusted splits invalidate economic interpretation.",
        "Gross and net portfolios compound separately; their terminal equity difference includes compounding, not only summed costs.",
        "Final positions are marked at the last close without forced liquidation or exit costs.",
        "Changing parameters after viewing holdout results invalidates an out-of-sample claim. No optimization is performed.",
    ]
    if config["synthetic"]:
        warnings.insert(0, "Synthetic demonstration data: outcomes provide no empirical market evidence.")
    return {
        "workflow": "trading", "results": results, "checks": checks, "warnings": warnings,
        "assumptions": {
            **config, "data_start": rows[0]["date"], "data_end": rows[-1]["date"],
            "observations": len(rows), "strategy": "long when close > trailing simple mean; flat otherwise",
            "signal_information": "Current and previous completed closes only; equality means flat",
            "execution": "At next observed session open; signals at final close cannot execute",
            "rebalance": "Daily target assessment; trade only when flat/long state changes",
            "benchmark": "Buy at first open after lookback completed closes; hold to final close",
            "position_sizing": "All available cash into fractional shares, including buy fee; no leverage or shorting",
            "cash_return": 0.0, "dividends": "excluded", "fees": "basis points of actual filled notional each side",
            "slippage": "adverse basis points from quoted open each side",
            "period_boundary": "Continuous portfolio; holdout starts from previous close equity, including overnight P&L",
            "drawdown": "Positive maximum close-equity drawdown from running peak including period opening equity",
            "turnover_definition": "Sum of absolute traded quantity times quoted open divided by pre-trade open equity",
            "return_units": "fractions, not percent; no annualization or inferred sessions-per-year",
            "selected_parameters": "Fixed before simulation; no parameter search",
        },
    }
