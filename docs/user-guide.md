# Using Agenthon Quant Lab

In an activated Python 3.12+ virtual environment, run the published toolkit from any writable directory.

```sh
python -m pip install agenthon-quant-lab==0.3.1
quant-lab doctor
quant-lab btc-study
```

To reproduce the later **cost break-even study**, use its [pinned development wheel instructions](../experiments/btc-cost-break-even-v1/README.md). That study produces a cost grid, crossing brackets and a figure.

The first install needs access to PyPI. The study runs offline with the bundled snapshot and references, independently checks the results and prints three paths. Start with `report.md`, explore the daily records in `dashboard.html`, and inspect the eight comparisons in `reproduction.json`. Use `quant-lab btc-study --out <new-directory>` to choose the destination. [Release and qualified platforms](releases/v0.3.1-pypi.md) · [Study report](../reports/btc-financial-v1/README.md) · [Protocol](../experiments/btc-financial-v1/protocol.json)

`quant-lab doctor` identifies an installed distribution or a development checkout, verifies dependency imports and checks bundled resources. `doctor --json` gives structured diagnostics. CSV works with the base package. For Parquet input, install `python -m pip install 'agenthon-quant-lab[parquet]==0.3.1'` in the same environment. Source development and the optional Codex skill have their own setup. [Developer guide](development.md) · [Skill guide](plugin-guide.md)

```sh
quant-lab example options --out runs/first-options
quant-lab example trading --out runs/first-strategy
```

The examples load their specifications and data from the installed package. Choose a fresh output path for each run.

## Run a historical portfolio comparison

The [historical guide](historical-workflow.md) walks through inspecting a local price file, choosing eligible periods, evaluating the portfolios, reading the CSV/SVG paths and reproducing the saved result. Use `quant-lab example historical --out runs/btc-q2` for the bundled Bitstamp sample. A separate `example trading` run uses two periods of synthetic prices. [Fixture attribution and transformation](../examples/data/bitstamp/README.md)

## Supply assumptions and read results

Copy the [option specification](../examples/options.json) or [trading specification](../examples/trading.json) to your own directory. For a trading run, supply a matching data file relative to the specification.
Read [option conventions](options-conventions.md) or
[trading conventions](trading-conventions.md) before changing it. Rates and
volatility are decimals, maturity is a year fraction, and dividend treatment must
be explicit. Trading requires user-provided CSV/Parquet with ordered session dates
and positive open/close prices, declared adjustment treatment and chronological
periods. Do not choose parameters after inspecting the final holdout.

```sh
quant-lab run path/to/spec.json --out runs/my-analysis
quant-lab explain runs/my-analysis
```

Open `report.md` for prices or portfolio/period tables, then inspect failed and
unavailable checks. `run.json` retains assumptions, provenance, complete results,
versions and timing. A passed run can have unavailable checks: it does not prove
input-source accuracy, predictive accuracy or trading profitability. The original `example trading` data is synthetic and its losing result is retained. `example historical` uses licensed BTC/USD observations.

## Reproduce or change one assumption

```sh
quant-lab verify-inputs runs/my-analysis
quant-lab reproduce runs/my-analysis --out runs/repeated
quant-lab reproduce runs/my-analysis --out runs/changed --set 'volatility=0.3'
```

Exact reproduction requires the saved source fingerprint. An old run may correctly
refuse the newer toolkit source. Use a **separate checkout** at the run record's
`code.git_commit` with its recorded dependency versions; preserve your current
checkout and the original run. For frozen v0.1 records, the immutable `v0.1.0` tag
contains the original engine. For v0.2 runs, use the published `v0.2.0` tag or the exact commit recorded in `run.json`. There is no fingerprint bypass. Changed assumptions
are recorded as a derived experiment, not an exact reproduction. The frozen BTC workflow has a separately verified [distribution compatibility record](../packaging/btc-compatibility.json).

## Search research and historical experiments

```sh
quant-lab archive papers "pricing"
quant-lab archive papers --status deferred --json
quant-lab archive experiments "momentum" --json
quant-lab archive experiments --status failed
```

These commands search only the curated local `research/papers.json` and
`experiments/experiments.json`; they do not retrieve papers or rerun experiments.
Paper status means `adaptation_status` (for example implemented, inspiration,
proposed or deferred). Experiment status describes the recorded outcome. Inspect
its evidence category, denominator, deployment and unknowns before comparing it
with another record. Local live, official reported, synthetic, incomplete and
not-run evidence remain different categories. An archived official score is not
a newly verified result or a Quant Lab performance claim.

## Package a run privately

```sh
quant-lab bundle runs/my-analysis --out bundles/my-analysis.zip
```

The ZIP includes the saved report/record/specification, validated results when
present, and the recorded **input snapshots, potentially your private data**.
Its manifest labels it private and hashes every included file. It also retains
local provenance paths. No upload or public sharing is performed. Review data
rights and disclosure before sharing; this command is not the sanitized public
archive exporter.

Bundling checks saved input/specification hashes and result consistency, but does
not rerun calculations or certify a record's authenticity. It rejects symlinks,
external snapshot paths, changed inputs/results, an existing output ZIP and output
inside the saved run. Unrelated neighboring files are excluded. The original run
is unchanged. Content is capped at 128 MiB. Public website exports are a separate,
curated artifact with their own provenance and publication review.
