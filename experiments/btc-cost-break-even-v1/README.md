# Reproduce the cost break-even study

The [frozen protocol](protocol.json) defines a descriptive re-analysis of the five retrospective Bitstamp BTC/USD evaluation years. The [report](../../reports/btc-cost-break-even-v1/README.md) contains the pooled crossings, annual comparisons, limitations and source identities.

## Run the published study

In an activated Python 3.12+ environment, run from any writable directory. Installation needs PyPI access. All study inputs and reference data are bundled.

```sh
python -m pip install agenthon-quant-lab==0.4.0
quant-lab doctor
quant-lab btc-cost-break-even --out btc-cost-review
```

Open `btc-cost-review/README.md` and `crossings.svg`. Inspect `grid.json` for all five portfolios and five calendar folds at each of 41 coarse settings, `refinements.json` for additional replays, `crossings.json` for brackets, `verification.json` for accounting and anchor comparisons, and `run.json` for source and artifact hashes. The output directory must be new. After installation the study runs offline.

The original report and public exhibit keep the development build’s provenance. Each new run records the executing package version. [Original development qualification](qualification.md) · [v0.4.0 package and qualification](../../docs/releases/v0.4.0.md)

The derived data, report and figure use CC BY-SA 4.0. The inputs are the original Zielak (mczielinski) Kaggle v706 data normalized by ff137 and aggregated to trade-bearing UTC session proxies. [Source and transformations](../btc-financial-v1/README.md#attribution-and-redistribution)
