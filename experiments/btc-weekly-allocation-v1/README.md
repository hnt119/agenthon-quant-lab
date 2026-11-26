# Reproduce the weekly allocation comparison

Does resetting BTC to 50% of post-cost wealth on positive-signal Mondays reduce the worst decline beyond putting half the starting capital in weekly momentum? On the previously examined 2020–2024 Bitstamp history the target had a 45.02% drawdown versus 64.45% for the half-funded account. The target ended with $4,008 less per $10,000 invested. [Report and drawdown chart](../../reports/btc-weekly-allocation-v1/README.md) · [Pre-evaluation freeze](protocol.json)

## Run the released study

Use a fresh Python 3.12+ virtual environment. Install the release from PyPI, then run from any writable directory. The wheel bundles the frozen dataset and required references.

```sh
python -m pip install agenthon-quant-lab==0.5.0
quant-lab doctor
quant-lab btc-weekly-allocation --out runs/allocation
```

Open `runs/allocation/README.md` for the result and `drawdown.svg` for the figure. `metrics.json` covers every account, cost setting, year and pooled period. The compressed daily ledger records decisions, trades, fees, shares and balances. The `target_for_open` field refers to total-account weight for the Monday target and to the active sleeve's binary instruction for the half-funded control. The verification and run receipts identify the checks, source and hashes. Each reproduction needs a new output directory. [Stable package qualification](../../docs/releases/v0.5.0.md) · [Original development qualification](qualification.md) · [Accounting evidence](../../reports/btc-weekly-allocation-v1/verification.json) · [Run receipt](../../reports/btc-weekly-allocation-v1/run.json)

## Check the public exhibit

From the review checkout, run the saved-result audit against the historical report or a fresh output directory.

```sh
python scripts/check_allocation_exhibit.py reports/btc-weekly-allocation-v1
```

The accounting verifier checks five accounts against the dated source observations. A separate day-by-day bootstrap reconstructs the fixed cash reserve after every resampled return and checks the reported interval. The exhibit audit compares the three existing baseline ledgers under every cost setting, checks 90 period summaries and traces the chart to daily total wealth. The website receives only the checked public projection.

## Next evidence

A prospective paper-observation protocol would test whether the risk and wealth trade-off persists through a new sequence of BTC prices. Before the first eligible Sunday, register the two unchanged allocation rules, a fixed observation horizon, the quote and cost convention, the treatment of missed observations, and a minimum evidence rule for interpreting drawdown. Record each scheduled paper decision at the time, including holds and omissions. Keep the cash sleeve fixed, avoid retrospective filling of missed decisions, and assess both accounts at the registered horizon. A short period with no meaningful decline would leave the risk question open. No prospective collection or trading was started here.

Zielak (mczielinski), Kaggle v706, normalized by ff137. Derived data, exhibits and reports are distributed under CC BY-SA 4.0. [Source and transformation notices](../../DATA-NOTICES.md)
