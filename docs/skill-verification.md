# Skill forward test — 2026-11-14 Singapore time

An independent implementation agent followed `skills/quant-research/SKILL.md`
and its referenced conventions to execute four realistic requests through
`scripts/quant.py`. These are offline functional/behavioral checks, not a live
model or automatic skill-selection evaluation. Every run recorded zero model
calls, zero tokens and zero billed cost. No competition material was used.

The tested pre-release source fingerprint was
`222b50590462866850590f4ef520204a532b6ffb576ccb633fe8c4be9ac5d7a1`.
Git identity was `null` because these checks preceded repository creation.
Python was 3.12.7; reported numerical dependencies were NumPy 2.5.4,
SciPy 1.18.1, and PyArrow 26.0.1. Final release qualification is separately
recorded against the committed version; this initial trace is not that receipt.

## Requests and observed behavior

| Request | Observed result | Checks and artifact |
|---|---|---|
| Price USD 100 spot/strike, one year, continuous rate 5%, dividend yield zero, volatility 20%; show 10/20/30% scenarios | Call 10.45058357; put 5.57352602. Scenario call values 6.80495771 / 10.45058357 / 14.23125479; put values 1.92790016 / 5.57352602 / 9.35419724. Vega units explicitly per unit decimal volatility. | Exit 0; 72 passed, 0 failed, 0 unavailable. `options/report.md` and `options/run.json`. |
| Compare the fixed example strategy with buy-and-hold after costs | SMA20 gross return −6.4307%, net −9.0143%; buy-and-hold gross −4.9485%, net −5.0435%. Losses preserved. Synthetic data explicitly disclosed. Fees/slippage both 5 bps per side. | Exit 0; 24 passed, 0 failed, 1 unavailable: input provenance/adjustment independent verification. `trading/report.md` and `trading/run.json`. |
| Explain the negative-volatility example failure | `explain` identifies “maturity_years and volatility must be nonnegative.” Request snapshot contains volatility −0.2. Smallest supported correction is a nonnegative volatility in a new run; the failed run remains intact. | Run exit 2, explain exit 0; one failed input check. `invalid/report.md` and `invalid/run.json`; no `validated-results.json`. |
| Reproduce the saved option experiment with volatility changed to 30% | New call 14.23125479 and put 9.35419724. Parent remains volatility 20%; derived record names exactly the volatility change and hashes the parent's run record. It is a changed-assumption experiment, not exact reproduction. | Exit 0; 72 passed. `options-vol30/report.md` and `options-vol30/run.json`. |

Trading development is 2025-01-02 through 2025-06-18; holdout is 2025-06-19
through 2025-09-10. Net SMA returns are −3.2125% and −5.9944%; net benchmark
returns are −0.6402% and −4.4316%, respectively. Benchmark first investment
follows the same warmup period. No parameter adjustment followed these losses.
These synthetic outcomes establish execution/accounting mechanics only.

Additional assertions checked the option parity identity, increasing values
across the chosen volatility scenarios, 30% derived values equaling the
original 30% scenario, every trading open target matching the prior close
target, the unchanged parent's SHA-256, failure-artifact retention, and zero
model usage. All assertions passed.

## Actual local evidence

Artifact root:
`/private/var/folders/yj/kb0lxp3n3079tw_kj4r8p_l40000gn/T/quant-skill-forward-ibnj957b`.
This is a temporary local test location, not a permanent published report.
It contains `transcript.json` with exact commands, exit codes, stdout/stderr,
and `assertions.json` with observed values and artifact hashes. Successful
runs contain input snapshots, `spec.json`, `run.json`, `report.md`, and
`validated-results.json`. The invalid run omits the validated-results artifact.

The helper was
`/private/tmp/agenthon-quant-lab-stage/skills/quant-research/scripts/quant.py`.
Commands were `run <absolute-spec> --out <fresh-directory>`,
`reproduce <options-directory> --out <fresh-directory> --set volatility=0.3`,
and `explain <invalid-directory>` as documented in the skill.

| Run | `run.json` SHA-256 |
|---|---|
| options | `35e9c1c7d41aabd896fc910c24f9b32f25700e36b7c6c225a905db444ad5cc57` |
| options-vol30 | `b94ae618ab84554f689cd432f828fc5e37a713c4efe1607faf575f7ffa8ccad5` |
| trading | `a54fe3a9d4d3fc7c5fdfb373cfff3ee2272de2ff9eaf432c3595222d20d6ca95` |
| invalid | `160f5564d0e6ffb9d7805f61dcde00b3627e299e932b0bd80982081427475919` |

## Usability observation

All four commands and the referenced conventions were sufficient to complete
the requests. The initial options report was 730 lines because each scenario
embedded its full check list inside result JSON and the checks were listed
again later. The trading report was 357 lines of mostly structured JSON.
The tester recommended concise valuation/scenario and portfolio/period tables,
with detailed evidence retained in `run.json`. This is a readability finding,
not a numerical failure; the original test artifacts remain unchanged.
