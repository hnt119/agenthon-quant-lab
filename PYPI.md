# Agenthon Quant Lab

A local Python toolkit for asking whether a financial idea survives trading costs and comparison with a simple alternative. It grew out of Team 166’s Agenthon 2026 Track 1 work on independently checking generated financial programs. The package includes three reproducible BTC studies, European option pricing, spot-portfolio examples and a searchable research archive.

## Install and reproduce

Use an activated Python 3.12+ virtual environment and a writable working directory. The CLI runs independently of Git, Codex and API credentials. Each study uses bundled inputs and writes to a fresh folder.

```sh
python -m pip install agenthon-quant-lab==0.4.0
quant-lab doctor
quant-lab btc-study --out runs/momentum
quant-lab btc-cost-break-even --out runs/costs
quant-lab btc-weekly-cadence --out runs/weekly
```

Open `runs/momentum/report.md` and its offline `dashboard.html` to explore the original daily decisions. The follow-ups write `README.md` and a figure in each output folder. Their `verification.json` and `run.json` record accounting checks and artifact hashes. [Output guide](https://github.com/hnt119/agenthon-quant-lab/blob/v0.4.0/docs/user-guide.md) · [Release qualification](https://github.com/hnt119/agenthon-quant-lab/blob/v0.4.0/docs/releases/v0.4.0.md)

## Three questions on the same BTC history

The evaluation covers five previously examined calendar years, 2020–2024, on Bitstamp BTC/USD spot. At base costs every fill incurs a 50 bp fee and 10 bp adverse slippage. Prices are delayed minute-candle proxies. There are zero prospective observations.

1. **Did daily momentum beat passive BTC/cash?** A $10,000 daily momentum account finished at $39,414 after costs. The passive account finished at $70,715. Adding the fixed FFT filter reduced cumulative net return from +294.14% to +41.83%. The predictive-return and momentum-minus-passive Sharpe intervals both include zero. [Report](https://github.com/hnt119/agenthon-quant-lab/blob/v0.3.0/reports/btc-financial-v1/README.md) · [Protocol](https://github.com/hnt119/agenthon-quant-lab/blob/v0.3.0/experiments/btc-financial-v1/protocol.json)
2. **Where did costs reverse the comparison?** Increasing both fee and slippage along the declared cost path erased daily momentum’s net-Sharpe advantage over passive near 0.3071× base costs. Their ending wealth crossed near 0.4781×. These descriptive thresholds are conditional on that sample and cost ratio. [Report and figure](https://github.com/hnt119/agenthon-quant-lab/blob/364f042d0e056d73736f08dfb61cf3d9ff9b2bfd/reports/btc-cost-break-even-v1/README.md) · [Protocol](https://github.com/hnt119/agenthon-quant-lab/blob/78f7486cbee975600b9d7f581533595f507a64f6/experiments/btc-cost-break-even-v1/protocol.json)
3. **Did weekly decisions help?** Monday execution using the completed Sunday signal cut fills from 188 to 80. Weekly finished at $48,686, above daily and below passive. Weekly maximum drawdown reached 73.34%, compared with daily’s 71.82%. Both weekly Sharpe comparisons have paired intervals spanning zero. [Report and figure](https://github.com/hnt119/agenthon-quant-lab/blob/cc751a9aaf65fb0d6fbc210bc317b18ae1abd91f/reports/btc-weekly-cadence-v1/README.md) · [Protocol](https://github.com/hnt119/agenthon-quant-lab/blob/997f4f7d7f0ea2932a3f9caa3d8233c3983ccfc4/experiments/btc-weekly-cadence-v1/protocol.json)

The independent checks cover information timing, trades, fees, BTC holdings, cash and closing marks. The economic evidence remains retrospective and inconclusive. [Portfolio walkthrough](https://hnt119.github.io/projects/quant-finance-agents/)

## Other commands

```sh
quant-lab example options --out option-example
quant-lab example historical --out historical-example
quant-lab archive papers FFT
quant-lab --help
```

CSV works with the base package. For Parquet input use `python -m pip install 'agenthon-quant-lab[parquet]==0.4.0'`. The optional Codex skill installs from its own tagged checkout. [Skill guide](https://github.com/hnt119/agenthon-quant-lab/blob/v0.4.0/docs/plugin-guide.md)

Software carries the Team 166 MIT notice. The 2017–2024 BTC study extract and financial derivatives use CC BY-SA 4.0. The separate Q2 2025 example uses CC BY 4.0. [Data sources, credits and licenses](https://github.com/hnt119/agenthon-quant-lab/blob/v0.4.0/DATA-NOTICES.md)
