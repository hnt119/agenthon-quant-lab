# Weekly study qualification

The [protocol](protocol.json) was committed at `997f4f7d7f0ea2932a3f9caa3d8233c3983ccfc4` before the new strategy was evaluated. The accounting implementation `92be1e16799594f7a7c07ef4d51196c9cac863ef` produced the [saved evidence](https://github.com/hnt119/agenthon-quant-lab/tree/cc751a9aaf65fb0d6fbc210bc317b18ae1abd91f/reports/btc-weekly-cadence-v1). Sources and inputs are identified in the run receipt and the complete implementation tree at that revision. The study uses the same admitted BTC history and original rules for daily momentum and the three passive controls.

## Numerical checks

- Ten synthetic tests exercised the original close signal, Sunday tie, first Monday delay, absence of unscheduled orders, year-boundary carry, future close perturbation and detection of corrupt source dates, fills and balances.
- The [accounting verifier](../../src/agenthon_financial/weekly_verify.py) reconstructed each weekly decision from dated raw closes. It independently solved for post-trade units and cash to check fees, timing, equity and calendar summaries. The 12 control paths matched their frozen daily ledgers under the original comparison rules.
- The separate [saved-result checker](../../scripts/check_weekly_study.py) compounded 5,481 weekly wealth marks from quote and close ratios. It reconciled all 90 portfolio-period-scenario summaries, all 36 Sharpe contrasts, both marginal intervals, exposure counts and the public metrics. It rejected an altered interval even after a matching exhibit and artifact hashes were supplied. Both base-cost paired intervals span zero.
- The 153-test local source suite passed. The original BTC and cost protocols and recorded output directories had zero source-control differences against the cost-study review head.

## Installed development distribution

The review build uses the package inputs at `2021ae82b73258d6f1bdbc19b4a49d091514b02c`. Local builds passed strict metadata verification. The direct wheel and the wheel rebuilt from the source distribution had identical member names and bytes, including 25 resources, two licenses and 38 Python modules. Archive hashes identify the specific local builds.

| Qualified file | SHA-256 |
|---|---|
| `agenthon_quant_lab-0.4.0.dev2-py3-none-any.whl` | `163fe41973680a5bab7632f51c9b30281496993f0713213dc0e9328bcdacf24b` |
| `agenthon_quant_lab-0.4.0.dev2.tar.gz` | `f17cc5f326b5479aafedeb82a4a589db3bf7062f82710d370f3e9cf119fdf32f` |

A clean macOS arm64 Python 3.12.7 virtual environment ran the wheel outside the checkout, with no Git on the CLI path or PYTHONPATH dependency. Doctor, bundled examples, archive lookup, frozen original BTC workflow, cost grid and weekly study passed. The original eight reproduction outputs and the eight new weekly artifacts matched byte-for-byte. Run receipts have new timestamps and describe their own environments. The separately installed weekly run also passed the independent saved-result checker. See the [installation command](README.md).

## Website handoff and release boundary

The [public projection](../../site-export/btc-weekly-cadence.json) has SHA-256 `53fea182631ee02b81e2ace76e74618c07f954ec8161bc386176595eeeb9c468`. It supplies the three cost scenarios, 90 portfolio summaries, both net-Sharpe contrasts and their intervals, counts of differently invested days, source identities and data license. The [programme](../../site-export/programme.json) has SHA-256 `2c070e36f9a920be294ac6695d3f4b08a2b08148a02e8a824415e5640c8b1b63`. The portfolio selects these records, preserves its existing release and study routes, and labels this build as a development reproduction. The stable public package remains v0.3.1.

The new study stacks on the existing toolkit cost comparison. Once a parent merges, confirm the child's target and effective diff against the integrated parent and rerun its checks. A production release needs owner authorization of the version and qualified assets under the existing release workflow. Preserve historical tags and assets. A separate stable version would require new metadata, builds, hashes and installed qualification.
