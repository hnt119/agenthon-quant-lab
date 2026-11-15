---
name: quant-research
description: "Price European options, inspect local daily CSV or Parquet prices, compare historical SMA, buy-and-hold and cash portfolios, reproduce saved runs, and explain relevant research and validation failures with Agenthon Quant Lab."
---

# Quant Research

Use the shared engine in the source checkout containing this skill. Resolve this
file's real path when installed through a symlink. `scripts/quant.py` locates the
checkout and `.venv`; it contains no finance calculations. Start with `doctor`.
If setup is missing, follow [setup and usage](../../docs/user-guide.md) and
[skill installation](../../docs/plugin-guide.md). `scripts/setup.py` installs
free dependencies; skill installation is optional and preserves existing links.

For modeling, read [option conventions](../../docs/options-conventions.md);
for strategy evaluation, read [trading conventions](../../docs/trading-conventions.md).
Use `examples/options.json` or `examples/trading.json` as the schema starting point. For daily market data and train/validation/test portfolios, use `examples/historical.json` and [the historical guide](../../docs/historical-workflow.md). Run `inspect-data <absolute-spec>` first and report timing, mapped fields, provenance and material calendar gaps.
Ask for missing inputs that materially affect results and expose chosen assumptions.
Do not guess rate units, dividend treatment or price-adjustment semantics.

Invoke `python3 <skill>/scripts/quant.py run <absolute-spec> --out <new-directory>`.
For a bundled demonstration, use `example options|trading|historical --out <new-directory>`. Historical runs also save `equity-drawdown.csv` and `equity-drawdown.svg`; link these with the report when the user asks how equity or drawdown changed. Include the data attribution when showing the Bitstamp sample.
Read `run.json` and `report.md`, including failed and unavailable checks. Link the
actual report and state conventions, results, periods and limitations. A nonzero
exit can still produce a useful failure report; preserve it before correcting inputs.

Use `explain <run-dir>` for a failure and inspect its request snapshot. Use
`reproduce <run-dir> --out <new-dir>` for reproduction; add `--set 'volatility=0.3'`
only for an intentional changed-assumption experiment. A fingerprint mismatch
requires a separate checkout of the recorded source and dependencies, never a
bypass. See [worked requests](references/requests.md).

For research context, query `archive papers "topic" --json`; for prior outcomes,
query `archive experiments "topic" --json`. `--status` filters paper adaptation
status or experiment outcome status. Retrieve only matching records and linked
references. Separate implemented results from hypotheses, and official reported,
local live, synthetic, incomplete and not-run evidence. Historical scores are not
newly verified performance. Do not load the competition archive into solver context.

If asked to package a run, `bundle <run-dir> --out <new.zip>` creates a **private**
bundle containing input data and local provenance. It does not sanitize for public
sharing or upload anything. Keep the ZIP outside the immutable run directory.

Keep calculations and checking in the shared engine. Checks establish numerical
or accounting properties, not profitability; synthetic examples establish mechanics
only. Preserve losses and never tune on the final holdout. American options,
discrete dividends, multiple assets, forecasting and live orders are unsupported.
Model assistance remains mock-only with zero paid budget; do not read credentials,
call model endpoints, execute generated code or run competition evaluators.
