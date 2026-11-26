# Reproduce the weekly BTC decision study

Does one scheduled decision per week improve momentum after costs? The Sunday-close rule made 80 fills over 261 opportunities, compared with 188 daily fills. At base costs it finished above daily momentum and below passive BTC/cash. Both paired Sharpe intervals include zero. The holdings differed at 292 of 1,827 closing marks. [Report and figure](../../reports/btc-weekly-cadence-v1/README.md) · [Frozen protocol](protocol.json)

## Run the development build

Use an activated Python 3.12 environment with Git for the initial source install. These commands build the pinned package, install it, and run from your current writable directory. The inputs are bundled. After installation, reproduction works offline and requires neither a checkout nor credentials.

```sh
python -m pip wheel --no-deps -w wheelhouse 'git+https://github.com/hnt119/agenthon-quant-lab.git@2021ae82b73258d6f1bdbc19b4a49d091514b02c'
python -m pip install wheelhouse/agenthon_quant_lab-0.4.0.dev2-py3-none-any.whl
quant-lab doctor
quant-lab btc-weekly-cadence --out btc-weekly-review
```

Choose a new output directory on each run. Read `README.md` and `weekly-cadence.svg` first. `comparisons.json` gives both contrasts by period and cost, the base-cost marginal intervals and the exposure counts. `metrics.json` contains all five accounts, three costs, five annual folds and the pooled history. `ledger.jsonl.gz` contains dated trades and cash, BTC and closing equity on every day. The verifier reconstructs scheduled signals from dated raw closes and balances from quote-side cash flows. `verification.json` reports its coverage and `run.json` identifies the inputs, source revision and outputs.

The public PyPI version **0.3.1** reproduces the original study with `quant-lab btc-study`. The weekly and cost-crossing commands are development capabilities. [Published release](https://pypi.org/project/agenthon-quant-lab/0.3.1/) · [Cost-crossing study](../btc-cost-break-even-v1/README.md)

## Inspect the evidence

From the review checkout, run the independent audit below on either the saved report directory or a fresh reproduction. It reconstructs wealth from quote and close ratios and reproduces paired intervals from the sampled daily returns.

```sh
python scripts/check_weekly_study.py reports/btc-weekly-cadence-v1
```

The [results](https://github.com/hnt119/agenthon-quant-lab/tree/cc751a9aaf65fb0d6fbc210bc317b18ae1abd91f/reports/btc-weekly-cadence-v1) preserve the [pre-evaluation freeze](https://github.com/hnt119/agenthon-quant-lab/blob/997f4f7d7f0ea2932a3f9caa3d8233c3983ccfc4/experiments/btc-weekly-cadence-v1/protocol.json). This study uses the same previously examined 2020–2024 Bitstamp BTC/USD spot history. The two intervals estimate within-sample uncertainty conditional on those years and trading paths. Prospective performance is unmeasured.

Zielak (mczielinski), Kaggle v706, normalized by ff137. The derived daily inputs, reports, figure and public financial projection carry CC BY-SA 4.0. [Source, transformations and redistribution](../btc-financial-v1/README.md#attribution-and-redistribution)
