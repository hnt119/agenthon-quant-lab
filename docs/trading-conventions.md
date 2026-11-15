# Trading workflow conventions

This is a deterministic, single-asset research simulation. It performs no
order placement, model inference, data download, parameter search, or training.
The default strategy is long-only SMA20; an explicitly supplied `lookback`
changes the experiment and must be chosen before inspecting the holdout.

The original `trading` workflow uses development and holdout periods. For the v0.3 `historical` workflow, use its three-period specification, dataset inspection and path exports. Both use the signal timing and cash accounting below. [Historical workflow](historical-workflow.md)

## Specification and input

Use `examples/trading.json` as the complete specification. Unknown fields are
rejected. `data` is a CSV or optional Parquet file with `date`, `open`, `close`.
The run wrapper resolves its path relative to the specification. Dates are
unique, strictly increasing ISO `YYYY-MM-DD` session labels. Prices must be
finite and positive; the engine neither sorts nor fills missing rows. Extra
columns are ignored. A gap means the next available observation, not a known
exchange session; completeness is unverified. CSV headers must be unique.
Parquet requires the optional PyArrow dependency and accepts strings or Arrow
date values; intraday timestamps are unsupported.
v0.1 caps each input at 10,000 observations to bound the four detailed ledgers.

`source` is a required provenance declaration. `timestamp_convention` is
`session_date`. `price_adjustment` must be `unadjusted` or `split_adjusted`.
Both opens and closes must use the same basis. Split-adjusted prices represent
synthetic adjusted units; quantities are not actual historical shares. No
dividends, dividend reinvestment, interest, taxes, splits in raw prices,
currency conversion, market impact, liquidity limits, or minimum lots are
modeled. Total-return/dividend-adjusted series are not supported. Source,
corporate-action treatment, completeness and tradability are user declarations
and are explicitly marked **unavailable** for independent verification.

`development_end` and `holdout_start` must be actual consecutive observed dates.
Development includes at least one post-warmup observation and holdout is
nonempty. Portfolios continue across the boundary; nothing is reset or fitted.
The engine reports full, development and holdout metrics, retaining losses.
This does not prove parameters were selected without prior knowledge of data.

## Signal and execution

At completed close `t`, calculate the arithmetic mean of the latest `lookback`
closes including `t`. Target long if close is strictly greater than the mean;
otherwise target flat. During warmup target flat. The target executes at the
**next observed session's open**, never the signal day's open. A final-close
signal is recorded but cannot execute. Each open has at most one trade.

Buy with all cash when the prior close target is long and the position is
flat. Sell all shares when that target is flat and a position is held. Holding
a long target does not rebalance shares. Fractional shares are allowed, with
no short selling or leverage. Cash earns zero. Buy-and-hold buys at the first
open after `lookback` completed closes and holds; it uses the same fees,
slippage, warmup start, and final marking as the strategy. It is not the raw
asset return starting at the first input close.

Let `f = fee_bps / 10000`, `s = slippage_bps / 10000`, and `O` be quoted open.

- Buy fill is `O * (1 + s)`; buy quantity is `cash / (fill * (1 + f))`.
- Sell fill is `O * (1 - s)`; proceeds are `quantity * fill * (1 - f)`.
- Fee is `absolute quantity * fill * f`; slippage cost is
  `absolute quantity * abs(fill - O)`.
- End-of-day equity is `cash + shares * close`.
- P&L reconciles to overnight P&L plus intraday P&L minus fees and slippage.

Fees and slippage each apply on both sides and must be below 10000 bps.
Gross and net portfolios compound separately. Their ending equity difference
is a cost drag with compounding; it is generally different from summed fees
and slippage. Final positions remain open and are marked at the last close;
there is no assumed terminal liquidation or exit charge.

## Metrics and checks

Returns are fractions rather than percentage points. No annualization assumes
a trading calendar. Maximum drawdown is positive and uses close equities,
including period starting equity in the peak. Holdout starts from the last
development close equity, so its first day's return includes overnight P&L.
Exposure is end-of-day market value divided by equity. Reported turnover sums
`abs(trade quantity) * quoted open / pre-trade open equity`; each entry and
exit contributes. Transaction costs are fees plus adverse slippage dollars.
The simulator supplies balances, trades, signal dates, costs, and P&L for each
observation, alongside gross and net buy-and-hold comparison.

The read-only verifier independently reconstructs balances from reported
trades and original quotes, checks close targets and next-open execution,
recomputes fee/slippage and P&L identities, and enforces long-only cash
constraints. Base tolerances are absolute `1e-7`, relative `1e-10`, explicitly
recorded per check. Cash and P&L cancellation checks additionally allow eight
floating-point ULPs at the scale of the original cash/notional or equity
operation. This permits representational roundoff on large portfolios without
using a portfolio-percentage allowance for a near-zero balance. An all-cash buy
clamps only its residual within that eight-ULP bound to zero; the verifier uses
independently reconstructed cash flows and the same documented precision
bound, never modifying supplied ledger records. Nonfinite summary metrics are
rejected even when each individual ledger value is finite. Corrupted outputs
are reported, not silently repaired.
These checks validate accounting and stated mechanics, not a trading edge.

Authored regression cases cover a six-session hand calculation, fees/slippage,
altered future observations leaving earlier decisions unchanged, corrupted
cash/P&L/timing/fees, duplicate entries, unexecuted final signals, invalid input,
period compounding, and CSV/Parquet equivalence when PyArrow is installed.
The tiny fixture makes 10 shares at 12, marks at 15 then 9, sells at 9, and
finishes with 90 from 120 before costs. It intentionally loses 25% and is not
derived from any competition fixture or answer.

Historical inspiration is limited to the general accounting and chronology
lessons in the original project's `docs/TRADE_ACCOUNTING_GATE_HANDOFF.md`,
`docs/PENDING_EXIT_ENTRY_GATE_HANDOFF.md`, and
`docs/BOLLINGER_TRADE_SEQUENCE_REVIEW.md`. No competition data, checker code,
reference values, task answers, or provider credentials enter this workflow.
