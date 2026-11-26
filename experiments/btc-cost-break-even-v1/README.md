# Reproduce the cost break-even study

The [frozen protocol](protocol.json) defines a descriptive re-analysis of the five retrospective Bitstamp BTC/USD evaluation years. The [report](../../reports/btc-cost-break-even-v1/README.md) contains the pooled crossings, annual comparisons, limitations and source identities.

## Install the reviewed study

Use an activated Python 3.12+ environment with Git and a writable working directory. The wheel contains the verified BTC inputs and both study protocols. These commands build the development version from the qualified package-input commit, install it, then reproduce the analysis outside a checkout.

```sh
python -m pip wheel --no-deps --wheel-dir wheelhouse 'git+https://github.com/hnt119/agenthon-quant-lab.git@9632d57cc499e41661703bfdcb7dc41dcd9f937a'
python -m pip install wheelhouse/agenthon_quant_lab-0.4.0.dev1-py3-none-any.whl
quant-lab doctor
quant-lab btc-cost-break-even --out btc-cost-review
```

Open `btc-cost-review/README.md` and `crossings.svg`. Inspect `grid.json` for all five portfolios and five calendar folds at each of 41 coarse settings, `refinements.json` for additional replays, `crossings.json` for brackets, `verification.json` for accounting and anchor comparisons, and `run.json` for source and artifact hashes. The output directory must be new. After installation the study runs offline.

The installation above is for the development study. The released PyPI version 0.3.1 reproduces the original five-year benchmark with `quant-lab btc-study`. [Published package](https://pypi.org/project/agenthon-quant-lab/0.3.1/)

The derived data, report and figure use CC BY-SA 4.0. The inputs are the original Zielak (mczielinski) Kaggle v706 data normalized by ff137 and aggregated to trade-bearing UTC session proxies. [Source and transformations](../btc-financial-v1/README.md#attribution-and-redistribution)
