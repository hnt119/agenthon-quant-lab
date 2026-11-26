# Qualification of the weekly allocation study

The historical run began from implementation commit `5a74b09ab6570847e894166776c4363618075524`, after protocol commit `cf2fa6ffc2a38f0b85cefa2545a53a65579507e7`. The [result commit](https://github.com/hnt119/agenthon-quant-lab/tree/bfaeada64e257c62943474065c3ae23b70bda23f/reports/btc-weekly-allocation-v1) contains all eight deterministic outputs and the timestamped run receipt. The development package was built from `57d7b49477066fd58006d7781823a00228c1d046`. The published v0.4.0 tag and the three earlier studies retain their original contents. The allocation calculation used no model calls, paid data, or prospective observations.

## Independent financial evidence

- Reconstructed five portfolios at three costs from raw close signals, delayed quotes, and fee/slippage arithmetic. The verifier checked 27,405 account-days, 90 pooled/annual summaries, and the sizing-control wealth and own-return identities on all 5,481 scenario-dates.
- The observed maximum drawdown contrast was +19.4306401123 percentage points. Two implementations agreed on the paired percentile endpoints +0.6555473107 and +23.8175336532. One compounds batches of paths and takes quantiles, the other steps each replicate forward by day and independently interpolates the endpoints. Both maintain the fixed cash reserve through all 4,000 draws. [Verified calculations](../../reports/btc-weekly-allocation-v1/verification.json)
- A separate read-only audit checked every dated row for the full weekly, daily and annually updated passive accounts against the original frozen ledger across all three costs. It recalculated the public first-fill weights, consecutive-positive trades, peak/trough observations, all displayed metric cells, both chart series at 63 dates and both trough markers. The split between sampled chart and full daily maximum is labeled on the figure. [Audit code](../../scripts/check_allocation_exhibit.py)
- All 163 source tests passed. Synthetic cases exercised both sides of a post-cost rebalance, a flat quote, an exit to zero, carry across December, initial waiting, future-data invariance, corruption of trades, costs and timing, and a hand-enumerated block resample. [Source checks](https://github.com/hnt119/agenthon-quant-lab/actions/runs/45838334184)

## Installation outside the checkout

The wheel and source distribution passed strict metadata checks. All 77 wheel members and 83 source-distribution files met the package allowlist. The 27 resources include the new frozen protocol and immutable earlier weekly summaries. The wheel rebuilt from the source distribution contained identical member contents.

| Local development artifact | SHA-256 |
|---|---|
| `agenthon_quant_lab-0.5.0.dev1-py3-none-any.whl` | `ba82535e0629fefc86d79f464ea430d97ec9b68a52b57197a9bd8dd08f8bdaa7` |
| `agenthon_quant_lab-0.5.0.dev1.tar.gz` | `552c5dc0310c44ec489c9b74973b2917cadc87ea0f6383a88a5d7110cacb2830` |

On macOS arm64 with Python 3.12.7, a fresh wheel installation outside the checkout passed doctor and all installed workflows with an isolated CLI path. All 24 previously frozen artifacts and all eight new allocation artifacts were byte-identical. A second fresh environment executed the [pinned Git installation](README.md) and the exact walkthrough command in an unrelated directory. Pip identified the expected revision, and all eight new files again matched the saved results byte-for-byte.

On hosted Linux with Python 3.12.16, all eight new artifacts also matched byte-for-byte. The earlier original study reproduced six of eight byte-for-byte and the remaining two within the established tolerances. The earlier cost grid was numerically equivalent, and its refinements, crossings and public export were byte-identical. The earlier weekly ledger, metrics, comparisons and public export matched byte-for-byte. [Installed Linux qualification](https://github.com/hnt119/agenthon-quant-lab/actions/runs/45838334214/job/139973028017)

The allocation exhibit SHA-256 is `13ebf97d67dde30420ae32566f96d423c8083fb18e7e9a3bb12ec8aca4c4334a`. Its publication in a review branch gives the portfolio a stable, attributable input. These checks establish reproducibility of the recorded retrospective comparison. They provide no observations of future performance.
