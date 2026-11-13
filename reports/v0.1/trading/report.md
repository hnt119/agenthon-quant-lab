# Agenthon Quant Lab — trading

**Status: passed** · v0.1.0 · 2026-11-13T17:03:23.933659+00:00

This is an offline calculation/simulation. Numerical checks do not establish predictive accuracy or trading profitability.

## Results

Returns include the initial warmup in cash. Both portfolios begin trading after the same warmup; final positions are marked without liquidation.

| Portfolio | Costs | Return | Max drawdown | Mean exposure | Turnover | Fees | Slippage | Final equity | Trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| strategy | gross | -6.4307% | 13.4287% | 42.22% | 28.0000 | 0.0000 | 0.0000 | 9356.9331 | 28 |
| strategy | net | -9.0143% | 15.1429% | 42.22% | 27.9860 | 136.9814 | 136.9813 | 9098.5729 | 28 |
| buy_and_hold | gross | -4.9485% | 15.9507% | 88.89% | 1.0000 | 0.0000 | 0.0000 | 9505.1523 | 1 |
| buy_and_hold | net | -5.0435% | 15.9507% | 88.89% | 0.9990 | 4.9975 | 4.9950 | 9495.6543 | 1 |

### Chronological periods

| Portfolio | Costs | Period | Start | End | Return | Drawdown |
|---|---|---|---|---|---:|---:|
| strategy | gross | development | 2025-01-02 | 2025-06-18 | -1.4545% | 8.5174% |
| strategy | gross | holdout | 2025-06-19 | 2025-09-10 | -5.0496% | 7.5854% |
| strategy | net | development | 2025-01-02 | 2025-06-18 | -3.2125% | 9.5182% |
| strategy | net | holdout | 2025-06-19 | 2025-09-10 | -5.9944% | 8.3218% |
| buy_and_hold | gross | development | 2025-01-02 | 2025-06-18 | -0.5408% | 11.1120% |
| buy_and_hold | gross | holdout | 2025-06-19 | 2025-09-10 | -4.4316% | 9.4512% |
| buy_and_hold | net | development | 2025-01-02 | 2025-06-18 | -0.6402% | 11.1120% |
| buy_and_hold | net | holdout | 2025-06-19 | 2025-09-10 | -4.4316% | 9.4512% |

Full position, cash, trade, cost and P&L ledgers are retained in `run.json`.

## Specification

```json
{
  "workflow": "trading",
  "data": "data/synthetic_prices.csv",
  "source": "Authored synthetic demonstration; scripts/generate_synthetic_data.py; Python random.Random seed 20261114; no market observations or exchange holiday calendar",
  "price_adjustment": "unadjusted",
  "timestamp_convention": "session_date",
  "initial_cash": 10000.0,
  "fee_bps": 5.0,
  "slippage_bps": 5.0,
  "lookback": 20,
  "development_end": "2025-06-18",
  "holdout_start": "2025-06-19",
  "synthetic": true
}
```

## Assumptions

```json
{
  "workflow": "trading",
  "data": "data/synthetic_prices.csv",
  "source": "Authored synthetic demonstration; scripts/generate_synthetic_data.py; Python random.Random seed 20261114; no market observations or exchange holiday calendar",
  "price_adjustment": "unadjusted",
  "timestamp_convention": "session_date",
  "initial_cash": 10000.0,
  "fee_bps": 5.0,
  "slippage_bps": 5.0,
  "lookback": 20,
  "development_end": "2025-06-18",
  "holdout_start": "2025-06-19",
  "synthetic": true,
  "data_start": "2025-01-02",
  "data_end": "2025-09-10",
  "observations": 180,
  "strategy": "long when close > trailing simple mean; flat otherwise",
  "signal_information": "Current and previous completed closes only; equality means flat",
  "execution": "At next observed session open; signals at final close cannot execute",
  "rebalance": "Daily target assessment; trade only when flat/long state changes",
  "benchmark": "Buy at first open after lookback completed closes; hold to final close",
  "position_sizing": "All available cash into fractional shares, including buy fee; no leverage or shorting",
  "cash_return": 0.0,
  "dividends": "excluded",
  "fees": "basis points of actual filled notional each side",
  "slippage": "adverse basis points from quoted open each side",
  "period_boundary": "Continuous portfolio; holdout starts from previous close equity, including overnight P&L",
  "drawdown": "Positive maximum close-equity drawdown from running peak including period opening equity",
  "turnover_definition": "Sum of absolute traded quantity times quoted open divided by pre-trade open equity",
  "return_units": "fractions, not percent; no annualization or inferred sessions-per-year",
  "selected_parameters": "Fixed before simulation; no parameter search"
}
```

## Verification

| Check | Status | Evidence |
|---|---|---|
| strategy.gross.ledger_shape_and_quotes | passed | All observations reconciled |
| strategy.gross.signal_and_execution_timing | passed | All observations reconciled |
| strategy.gross.cash_shares_equity_reconciliation | passed | All observations reconciled |
| strategy.gross.fee_slippage_reconciliation | passed | All observations reconciled |
| strategy.gross.pnl_reconciliation | passed | All observations reconciled |
| strategy.gross.long_only_cash_constraints | passed | All observations reconciled |
| strategy.net.ledger_shape_and_quotes | passed | All observations reconciled |
| strategy.net.signal_and_execution_timing | passed | All observations reconciled |
| strategy.net.cash_shares_equity_reconciliation | passed | All observations reconciled |
| strategy.net.fee_slippage_reconciliation | passed | All observations reconciled |
| strategy.net.pnl_reconciliation | passed | All observations reconciled |
| strategy.net.long_only_cash_constraints | passed | All observations reconciled |
| buy_and_hold.gross.ledger_shape_and_quotes | passed | All observations reconciled |
| buy_and_hold.gross.signal_and_execution_timing | passed | All observations reconciled |
| buy_and_hold.gross.cash_shares_equity_reconciliation | passed | All observations reconciled |
| buy_and_hold.gross.fee_slippage_reconciliation | passed | All observations reconciled |
| buy_and_hold.gross.pnl_reconciliation | passed | All observations reconciled |
| buy_and_hold.gross.long_only_cash_constraints | passed | All observations reconciled |
| buy_and_hold.net.ledger_shape_and_quotes | passed | All observations reconciled |
| buy_and_hold.net.signal_and_execution_timing | passed | All observations reconciled |
| buy_and_hold.net.cash_shares_equity_reconciliation | passed | All observations reconciled |
| buy_and_hold.net.fee_slippage_reconciliation | passed | All observations reconciled |
| buy_and_hold.net.pnl_reconciliation | passed | All observations reconciled |
| buy_and_hold.net.long_only_cash_constraints | passed | All observations reconciled |
| input_source_and_adjustments_independently_verified | unavailable | Source, completeness, tradability, and corporate-action treatment are user declarations; no data vendor verification was performed. |

## Warnings and limitations

- Synthetic demonstration data: outcomes provide no empirical market evidence.
- Historical or synthetic simulation does not establish predictive accuracy or trading profitability.
- No dividends, interest on cash, taxes, market impact, liquidity constraints, or minimum lot sizes are modeled.
- Open and close prices must use the same adjustment basis. Unadjusted splits invalidate economic interpretation.
- Gross and net portfolios compound separately; their terminal equity difference includes compounding, not only summed costs.
- Final positions are marked at the last close without forced liquidation or exit costs.
- Changing parameters after viewing holdout results invalidates an out-of-sample claim. No optimization is performed.

## Provenance and reproduction

Source commit: `ab2f62085f3c18ee97c555b8eb1bd6e400228ece`; runtime source dirty: `False`.

Source fingerprint (SHA-256, distinct from Git): `f07463aa017f4627188d9d83edc319fdfe221ba0919baf662cf5a0f7c073e397`.

Elapsed seconds: 0.061733. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.

Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).

From the repository root, using the documented environment:

```sh
python -m agenthon_quant reproduce reports/v0.1/trading --out runs/reproduced-NEW
```
