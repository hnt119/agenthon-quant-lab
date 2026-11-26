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


## Cost-crossing development study

This development build also provides `quant-lab btc-cost-break-even --out btc-cost-review`. It reruns the fixed Bitcoin portfolios across the declared fee and slippage grid, checks the accounting and writes a report, figure and machine-readable crossing brackets. The published v0.3.1 release supports the original `quant-lab btc-study` workflow. [Study protocol](https://github.com/hnt119/agenthon-quant-lab/blob/78f7486cbee975600b9d7f581533595f507a64f6/experiments/btc-cost-break-even-v1/protocol.json) · [Cost study report](https://github.com/hnt119/agenthon-quant-lab/blob/364f042d0e056d73736f08dfb61cf3d9ff9b2bfd/reports/btc-cost-break-even-v1/README.md)

## Weekly-decision development study

`quant-lab btc-weekly-cadence --out weekly-review` reproduces the development study of Sunday-close BTC momentum, with Monday execution, immutable baselines, three cost scenarios and paired uncertainty. The report, figure and accounting receipt are generated locally from bundled inputs. [Weekly protocol](https://github.com/hnt119/agenthon-quant-lab/blob/997f4f7d7f0ea2932a3f9caa3d8233c3983ccfc4/experiments/btc-weekly-cadence-v1/protocol.json)
