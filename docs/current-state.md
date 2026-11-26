# Current state

Version **0.5.0** supports four offline BTC reproductions in a single Python installation. The original command generates the Markdown report, daily-decision dashboard and comparison receipt. The cost, weekly cadence and allocation commands produce separate reports, figures, results and verification records. The optional Codex skill uses a separate tagged checkout. [Install and run](user-guide.md) · [v0.5.0 qualification](releases/v0.5.0.md)

All four analyses use the previously examined 2020–2024 Bitstamp BTC/USD history. Daily momentum finished below passive BTC/cash at base costs. Its Sharpe advantage over passive disappeared near 0.3071× the base fee and slippage along the declared path. Weekly decisions reduced fills and improved the observed base-cost result over daily momentum. Passive still finished ahead, drawdown was slightly deeper for weekly than daily, and both weekly Sharpe comparison intervals include zero. All fills use minute-candle proxies. The four historical reports contain zero prospective observations. [Daily and FFT results](../reports/btc-financial-v1/README.md) · [Cost thresholds](../reports/btc-cost-break-even-v1/README.md) · [Weekly comparisons](../reports/btc-weekly-cadence-v1/README.md)

The [six-study catalogue](../research/programme.json) records five completed comparisons across four retrospective runs. The fourth run is available in the [installed package](../experiments/btc-weekly-allocation-v1/README.md). Monday targeting reduced drawdown and terminal wealth versus the half-funded control. Cross-asset validation remains proposed. The separate controlled-model comparison is paused pending independent human adjudication. [Workbench and evidence boundaries](financial-workbench.md)

The toolkit also supports European option pricing and spot-portfolio examples. The daily-price workflow includes a separate 91-session Q2 2025 BTC/USD dataset under CC BY 4.0. The five-year study data and derived outputs carry CC BY-SA 4.0. [Historical guide](historical-workflow.md) · [Data notices](../DATA-NOTICES.md)

The curated public archive contains **12 papers and 18 experiment records**. Each observation includes its scope and provenance. The portfolio displays a sanitized projection and a bounded option calculator checked against Python. [Paper index](../research/papers.json) · [Experiment register](../experiments/experiments.json) · [Project article](https://hnt119.github.io/projects/quant-finance-agents/)

## Earlier releases

The original v0.1.0 release recorded 52 passing tests. The v0.2.0 release recorded 68 and an archive of 17 experimental records at that milestone. v0.3.0 introduced the source-based BTC workbench. [v0.3.1](releases/v0.3.1-pypi.md) added the installed-distribution workflow for that original study. Use each revision’s dated record when reproducing its results. [v0.1 manifest](../release-manifest.json) · [v0.2 release report](releases/v0.2.0.md) · [v0.3.0 qualification](releases/v0.3.0-review.md)

The prospective weekly allocation register follows two separate $10,000 paper accounts on new BTC/USD reference fixings. Its public status records completed and missed cycles, if any, with an as-of timestamp. [Observation protocol and dates](../observations/README.md) · [Public observation record](https://github.com/hnt119/agenthon-quant-lab/tree/observations/weekly-allocation-v1)
