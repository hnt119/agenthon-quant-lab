# Current state

The published **v0.3.1** Python package reproduces the five-year BTC/USD study outside a source checkout. It includes the licensed inputs and reference outputs. The CLI generates a fresh Markdown report, offline dashboard and reproduction receipt. The optional Codex skill uses a separate checkout. [Install and run](user-guide.md) · [PyPI](https://pypi.org/project/agenthon-quant-lab/0.3.1/) · [Release qualification](releases/v0.3.1-pypi.md)

The completed momentum and FFT comparisons share one retrospective 2020–2024 evaluation. Base-cost momentum trailed passive BTC/cash, and the FFT gate reduced net return further. The [study report](../reports/btc-financial-v1/README.md) gives the estimates and intervals. The [six-study catalogue](../research/programme.json) also records the [descriptive cost study](../reports/btc-cost-break-even-v1/README.md). On the same five years, momentum lost its net-Sharpe advantage over passive near 0.3071× the base fee/slippage assumption. Its wealth advantage lasted until 0.4781×. [Install and reproduce the development study](../experiments/btc-cost-break-even-v1/README.md) The separate controlled-model comparison remains paused pending independent human adjudication. [Workbench and evidence boundaries](financial-workbench.md)

The [weekly decision study](../reports/btc-weekly-cadence-v1/README.md) found fewer trades and a slightly higher base-cost Sharpe than daily momentum on the same five years. Passive BTC/cash had the higher Sharpe, and both comparison intervals include zero. [Development installation and reproduction](../experiments/btc-weekly-cadence-v1/README.md)

The toolkit also supports European option pricing and spot-portfolio examples. The daily-price workflow includes a separate 91-session Q2 2025 BTC/USD dataset under CC BY 4.0. The five-year study data and derived outputs carry CC BY-SA 4.0. [Historical guide](historical-workflow.md) · [Data notices](../DATA-NOTICES.md)

The curated public archive contains **12 papers and 18 experiment records**. Each observation includes its scope and provenance. The portfolio displays a sanitized projection and a bounded option calculator checked against Python. [Paper index](../research/papers.json) · [Experiment register](../experiments/experiments.json) · [Project article](https://hnt119.github.io/projects/quant-finance-agents/)

## Earlier releases

The original v0.1.0 release recorded 52 passing tests. The v0.2.0 release recorded 68 and an archive of 17 experimental records at that milestone. v0.3.0 introduced the released source-based BTC workbench. Use each revision’s dated record when reproducing its results. [v0.1 manifest](../release-manifest.json) · [v0.2 release report](releases/v0.2.0.md) · [v0.3.0 qualification](releases/v0.3.0-review.md)
