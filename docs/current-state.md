# Current state

The **v0.3.0rc1 review candidate** adds local CSV/Parquet inspection, three chronological evaluation periods, gross/net SMA, buy-and-hold and cash portfolios, and equity/drawdown exports. It includes a 91-session BTC/USD dataset with pinned provenance and CC BY 4.0 attribution. [Historical guide](historical-workflow.md) · [Example report](../reports/historical-q2/report.md)

## Published v0.2.0

The standalone v0.2.0 toolkit preserves the v0.1.0 implementation and historical reports.

Implemented: deterministic option pricing/Greeks/scenarios and SMA-versus-buy-and-hold research, strict input conventions, numerical/accounting checks, saved-run reproduction, setup and dependency diagnostics, bundled examples, private result bundles and searchable research/experiment archives.

The public archive contains 12 paper summaries and 17 experimental records. A generated, sanitized projection supports the existing portfolio project page. The browser calculator is a deliberately smaller zero-dividend European-option illustration, checked against the Python engine; it does not execute the plugin.

The v0.1.0 baseline had 52 tests. Its immutable evidence is [the original release manifest](../release-manifest.json). v0.2.0 passes 68 toolkit tests locally and in Linux CI and is [published on GitHub](https://github.com/hnt119/agenthon-quant-lab/releases/tag/v0.2.0). Final source, qualification and publication status are tracked in [the v0.2.0 report](releases/v0.2.0.md). That report, Git and GitHub are authoritative for final commits and current publication.

Limitations: synthetic data establishes no market edge; data provenance declarations are unverified; archived live-model evidence is historical and deployment-specific; unavailable checks stay explicit. No new model inference, official evaluation, Docker build, financial transaction or portfolio deployment is authorized for this milestone.

Start with [the documentation journey](index.md). The next milestone is [here](next-milestone.md).
