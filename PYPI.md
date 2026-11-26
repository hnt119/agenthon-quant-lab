# Agenthon Quant Lab

Reproduce a five-year BTC/USD study, price European options, or compare daily spot portfolios. The command-line toolkit runs locally and includes the data, frozen decisions and reference outputs needed to check the Bitcoin study. It grew out of the independent financial checks used in Agenthon 2026 Track 1.

## Install and run

In an activated Python 3.12 or newer environment:

```sh
python -m pip install agenthon-quant-lab==0.3.1
quant-lab doctor
quant-lab btc-study
```

Run from any writable directory. The command creates a new folder under `./runs` and prints paths to a Markdown report, an offline HTML dashboard and a reproduction receipt. Use `--out PATH` to choose a new destination. No Git checkout, API key or Codex installation is required. Install `agenthon-quant-lab[parquet]==0.3.1` for Parquet input. The Codex skill is optional and installs separately from a maintained source checkout. [Skill guide](https://github.com/hnt119/agenthon-quant-lab/blob/main/docs/plugin-guide.md)

## What the study found

In 2020–2024, a simulated $10,000 momentum account ended at $39,414 after costs. An annually rebalanced passive BTC/cash allocation ended at $70,715. Adding the frozen spectral filter reduced momentum’s cumulative return from +294.14% to +41.83%. The predictive and risk-adjusted comparisons both had uncertainty intervals spanning zero. All five folds are retrospective, and fills use delayed minute-candle prices. [Financial report](https://github.com/hnt119/agenthon-quant-lab/blob/v0.3.0/reports/btc-financial-v1/README.md) · [Protocol and source](https://github.com/hnt119/agenthon-quant-lab/tree/v0.3.0/experiments/btc-financial-v1)

## Other commands

```sh
quant-lab example options --out option-example
quant-lab example historical --out historical-example
quant-lab archive papers FFT
quant-lab --help
```

Software is MIT-licensed. The 2017–2024 BTC observations and derived outputs use CC BY-SA 4.0. The separate Q2 2025 example uses CC BY 4.0. The distributions include detailed notices. [Data attribution](https://github.com/hnt119/agenthon-quant-lab/blob/v0.3.0/docs/publication.md)
