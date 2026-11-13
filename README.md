# Agenthon Quant Lab

A small financial modeling and trading research engine built from lessons in
Agenthon 2026 Track 1. It turns explicit assumptions into deterministic
calculations, independent checks and reproducible reports. It works offline
without an LLM, credentials or a market-data subscription.

**v0.1 supports two complete workflows:**

- European vanilla option prices, delta/gamma/vega/rho/theta, and volatility
  scenarios. Checks include discounted bounds, put–call parity, independent
  payoff integration and finite-difference sensitivity convergence.
- A predetermined long-only moving-average strategy versus buy-and-hold on
  user CSV or Parquet data. Signals use completed closes and trade at the next
  observed open. Reports include gross/net returns, drawdown, exposure, turnover,
  costs, chronological periods and full cash/position/P&L ledgers.

## Setup and examples

Python 3.12 or newer is required. From this repository:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-verified.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m agenthon_quant run examples/options.json --out runs/options
.venv/bin/python -m agenthon_quant run examples/trading.json --out runs/trading
```

The first installation downloads free dependencies; calculations need no network.
`requirements-verified.txt` pins the environment exercised for this release.
For a compatible unpinned installation instead, use `pip install -e '.[parquet]'`.
PyArrow is optional if only CSV is used. Existing output directories are refused;
choose a new name for each experiment. Data paths are relative to the spec file.

Each run writes `run.json`, `report.md`, the effective `spec.json`, and hashed
input snapshots. Successful runs additionally write `validated-results.json`.
Failed runs keep diagnostics and return exit code 2. Passed, failed and unavailable
checks are reported separately; a passed run may include unavailable checks.

```sh
.venv/bin/python -m agenthon_quant reproduce runs/options --out runs/options-copy
.venv/bin/python -m agenthon_quant reproduce runs/options --out runs/options-vol30 --set 'volatility=0.3'
.venv/bin/python -m agenthon_quant verify-inputs runs/options
.venv/bin/python -m agenthon_quant run examples/invalid-options.json --out runs/invalid
.venv/bin/python -m agenthon_quant explain runs/invalid
```

The invalid example intentionally fails with negative volatility. Exact
reproduction verifies input hashes and the engine source fingerprint first;
changed assumptions are recorded as a derived experiment. Use a source checkout
and the recorded dependency versions to reproduce this release. Git commits,
source fingerprints and input hashes are distinct identities.

## Read the saved results

- [Option valuation and scenarios](reports/v0.1/options/report.md)
- [Strategy and buy-and-hold comparison](reports/v0.1/trading/report.md)
- [Deliberate input failure](reports/v0.1/invalid-options/report.md)
- [Changed volatility assumption](reports/v0.1/options-vol30/report.md)
- [Release verification](reports/v0.1/verification.json) and
  [deliberate corruption checks](reports/v0.1/deliberate-failures.json)

The bundled prices are **synthetic**, generated with a recorded seed and no
market observations. The SMA20 example loses money and underperforms buy-and-hold
after costs. That unsuccessful result is preserved; no parameter tuning was done.
It demonstrates research mechanics, not an empirical trading edge.

## Use the Codex skill

The maintained skill is [skills/quant-research](skills/quant-research/SKILL.md).
It translates supported requests into explicit specs, runs this engine and reads
its checks. It does not contain a second calculation implementation.

For discovery in another local Codex setup, link this folder into your skills
directory (preserve an existing skill with the same name):

```sh
ln -s "$PWD/skills/quant-research" "$HOME/.codex/skills/quant-research"
```

Example requests: “Price these options and show how value changes with
volatility,” “Compare this strategy with buy-and-hold after costs,” “Explain why
this analysis failed validation,” and “Reproduce this saved experiment with a
different assumption.” All four are exercised through the skill's CLI helper.
See [skill verification](docs/skill-verification.md).

## Verification and maintenance

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_release.py --out runs/verification-NEW
```

The release verifier runs the suite, both workflows, failure explanation, exact
reproduction, an assumption change, and deliberate price/cash corruptions.
Independent tests include tiny hand-calculated trades, future-data invariance,
CSV/Parquet equivalence, option boundaries, publication failure, input tampering
and zero-budget mock assistance. No official competition evaluation runs.

| Location | Purpose |
|---|---|
| `src/agenthon_quant/` | Calculation, verification, run records and CLI |
| `examples/` | Explicit specifications and redistributable synthetic data |
| `tests/` | Independent numerical/accounting and contract regressions |
| `skills/quant-research/` | Thin reusable skill, references and command helper |
| `reports/v0.1/` | Frozen first-release outputs and verification evidence |
| `docs/` | Conventions, architecture, source audit, lessons and handoff |

## Scope and relationship to Agenthon

The original `agenthon-track1-agent` repository remains the competition archive.
This is a separate repository with selected MIT numerical patterns and new
fixtures, not a cleaned copy of every candidate or a new competition submission.
The [reuse map](docs/reuse-map.md), [source inventory](docs/source-audit.json),
[negative results](docs/negative-results.md) and [attribution](docs/attribution.md)
explain what was carried forward and why. Historical official scores, local
model runs, synthetic infrastructure tests and proposals remain distinct.

Option values assume constant parameters and continuous dividend yield; discrete
dividends and American exercise are unsupported. Trading is single-asset,
fractional-share, long-only simulation: no dividends, tax, liquidity, market
impact, cash interest or live orders. Data provenance/adjustments are declared
by the caller and cannot be independently established from a file alone.
Numerical/accounting checks do not establish predictive accuracy or profitability.

Model assistance is mock-only with a zero default budget; real-model behavior
is untested. There is no generated-code executor, live data client or broker
connection. A full dashboard is a subsequent milestone. Read the
[architecture decision](docs/architecture.md),
[options conventions](docs/options-conventions.md),
[trading conventions](docs/trading-conventions.md),
[dashboard milestone](docs/next-milestone.md), and
[current handoff](docs/current-state.md).
