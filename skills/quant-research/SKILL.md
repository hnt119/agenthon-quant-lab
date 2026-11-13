---
name: quant-research
description: "Run and explain reproducible European option valuation, volatility scenarios, and long-only moving-average strategy comparisons with Agenthon Quant Lab. Use for supported financial modeling or backtest requests, saved-run reproduction, and validation failures; not live trading or broad strategy search."
---

# Quant Research

Use the shared engine in the repository containing this skill. Resolve this
file's real path first if the skill is installed through a symlink. The helper
`scripts/quant.py` locates that repository and its `.venv`; it contains no finance
calculations. If setup is missing, follow the repository README.

Translate the request into a JSON specification. For options, read
[option conventions](../../../docs/options-conventions.md); for strategy
evaluation, read [trading conventions](../../../docs/trading-conventions.md).
Use the corresponding repository `examples/*.json` as the schema starting point.
Ask for missing inputs that materially affect the calculation; expose assumptions
before using defaults. Do not interpret an unspecified rate as a percentage or
infer adjusted-price semantics from a filename.

Invoke `python3 <skill>/scripts/quant.py run <spec.json> --out <new-directory>`.
Use absolute paths for specs and outputs. The output directory must not exist.
Read `run.json` and `report.md`, including failed and unavailable checks. Link the
actual report in the response; state conventions, numerical results, limitations
and comparison periods. A nonzero exit can still produce a useful failure report.

For a saved failure, use `explain <run-directory>` and inspect its request snapshot.
Explain the failed requirement and the smallest supported correction. Preserve
the failed run. For reproduction, use `reproduce <run-directory> --out <new-dir>`;
an intentional change can use `--set 'volatility=0.3'` (JSON values). This verifies
input hashes and engine identity first. Never call a changed assumption an exact
reproduction, and never overwrite evidence. See [worked requests](references/requests.md).

Keep calculation and checking inside the engine. Supported checks establish
numerical/accounting properties, not predictive accuracy or profitability.
Synthetic examples establish mechanics only. Preserve losing strategy outcomes;
do not optimize on the final held-out period. American options, discrete cash
dividends, multiple assets, forecasting and live orders are unsupported in v0.1.

Model assistance is mock-only and paid-service budget is zero. The skill must not
read credentials, call model endpoints, execute generated code or run competition
evaluators. For a relevant historical failure, consult only the matching entry in
[verified lessons](../../../docs/negative-results.md); research proposals in
`docs/research-notes.md` remain hypotheses. Do not load the competition archive
into an analysis context.
