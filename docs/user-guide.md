# Using Agenthon Quant Lab

Start with a **source checkout** and Python 3.12 or newer. From its root:

```sh
python3 scripts/setup.py
.venv/bin/python -m agenthon_quant doctor
.venv/bin/python -m agenthon_quant example options --out runs/first-options
.venv/bin/python -m agenthon_quant example trading --out runs/first-strategy
```

Setup creates or reuses only the checkout's `.venv`, installs the free dependencies
in `requirements-verified.txt`, then installs this package in editable mode. The
first installation needs a package-download connection. It does not contact a
model, data vendor or broker. It stops on installation failure and never falls
back to modifying system Python. Existing non-virtualenv files or symlinks named
`.venv` are preserved. Re-running setup is supported.

`doctor` checks the interpreter, installed dependency versions and actual module
imports, source checkout, bundled data and optional Codex skill link. It performs
no model calls. Missing PyArrow affects Parquet only; CSV remains usable. The
example commands are functional numerical/accounting checks, beyond dependency
imports. `doctor --json` gives the same diagnostics as structured data.

The `example` command resolves bundled specifications relative to the installed
source checkout, so it works from any current directory when invoked with that
checkout's interpreter. The `--out` path is relative to your current directory.
Choose a fresh directory every time. On Windows the virtualenv interpreter is
`.venv\Scripts\python.exe`; examples above show macOS/Linux paths.

## Run a historical portfolio comparison

The v0.3.0rc1 [historical guide](historical-workflow.md) walks through inspecting a local price file, choosing eligible periods, evaluating the portfolios, reading the CSV/SVG paths and reproducing the saved result. Use `examples/historical.json` for the Bitstamp sample and `examples/trading.json` for the original two-period synthetic example. [Fixture attribution and transformation](../examples/data/bitstamp/README.md)

## Supply assumptions and read results

Copy `examples/options.json` or `examples/trading.json` to a new specification.
Read [option conventions](options-conventions.md) or
[trading conventions](trading-conventions.md) before changing it. Rates and
volatility are decimals, maturity is a year fraction, and dividend treatment must
be explicit. Trading requires user-provided CSV/Parquet with ordered session dates
and positive open/close prices, declared adjustment treatment and chronological
periods. Do not choose parameters after inspecting the final holdout.

```sh
.venv/bin/python -m agenthon_quant run path/to/spec.json --out runs/my-analysis
.venv/bin/python -m agenthon_quant explain runs/my-analysis
```

Open `report.md` for prices or portfolio/period tables, then inspect failed and
unavailable checks. `run.json` retains assumptions, provenance, complete results,
versions and timing. A passed run can have unavailable checks: it does not prove
input-source accuracy, predictive accuracy or trading profitability. The original `example trading` data is synthetic and its losing result is retained. `example historical` uses licensed BTC/USD observations.

## Reproduce or change one assumption

```sh
.venv/bin/python -m agenthon_quant verify-inputs runs/my-analysis
.venv/bin/python -m agenthon_quant reproduce runs/my-analysis --out runs/repeated
.venv/bin/python -m agenthon_quant reproduce runs/my-analysis --out runs/changed --set 'volatility=0.3'
```

Exact reproduction requires the saved source fingerprint. An old run may correctly
refuse the newer toolkit source. Use a **separate checkout** at the run record's
`code.git_commit` with its recorded dependency versions; preserve your current
checkout and the original run. For frozen v0.1 records, the immutable `v0.1.0` tag
contains the original engine. For v0.2 runs, use the published `v0.2.0` tag or the exact commit recorded in `run.json`. There is no fingerprint bypass. Changed assumptions
are recorded as a derived experiment, not an exact reproduction. Wheel layout or
arbitrary environment portability is not promised.

## Search research and historical experiments

```sh
.venv/bin/python -m agenthon_quant archive papers "pricing"
.venv/bin/python -m agenthon_quant archive papers --status deferred --json
.venv/bin/python -m agenthon_quant archive experiments "momentum" --json
.venv/bin/python -m agenthon_quant archive experiments --status failed
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
.venv/bin/python -m agenthon_quant bundle runs/my-analysis --out bundles/my-analysis.zip
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
