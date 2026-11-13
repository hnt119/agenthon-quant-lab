# Worked requests

All commands below use the helper from SKILL.md, an absolute specification path,
and a new output directory. The repository README documents installation.

## “Price these options and show how value changes with volatility.”

Collect explicit spot, strike, maturity in years, continuous annual rate,
continuous dividend yield, annual decimal volatility and currency. Set
`workflow=options`, `option_type=both` (or the requested side) and a declared
`volatility_scenarios` list. See `examples/options.json`. Inspect the valuation,
scenario table, parity, bounds, payoff quadrature and Greek sensitivity checks.
Vega is per unit decimal volatility: multiply by 0.01 for one percentage point.
Do not treat unavailable boundary Greeks as zero.

## “Compare this strategy with buy-and-hold after costs.”

Use `examples/trading.json`, changing `data` and provenance to the user's input.
Read the price-adjustment and execution conventions before choosing them. Use the
fixed SMA lookback or the user's explicitly chosen parameter, fixed before
evaluation. Report both gross and net metrics and both chronological periods.
Use the full cash/position/trade ledger if a result is surprising. Never imply
that synthetic bundled data establishes an edge.

## “Explain why this analysis failed validation.”

Run `explain /absolute/run`, read the failed check and request snapshot, and
distinguish invalid input, failed numerical/accounting checks and unavailable
checks. `examples/invalid-options.json` intentionally has a negative volatility:
the engine exits 2, saves the failure and publishes no validated results. Fix the
specification in a new file/run; do not edit the failed evidence.

## “Reproduce this saved experiment with a different assumption.”

Run `reproduce /absolute/run --out /absolute/new-run --set 'volatility=0.3'`.
For a trading cost comparison, use `--set 'fee_bps=10'`. The engine verifies
snapshot hashes and source fingerprint before applying the change; the derived
record identifies its parent and changes. The original run stays intact. Exact
reproduction omits `--set`; compare analysis results, not elapsed times or paths.

## “Find papers relevant to this pricing approach and show what is implemented.”

Run `archive papers "pricing" --json`, substituting the relevant topic. Read each
matching record's adaptation status and source link. Explain what the current
engine implements, what only inspired it, and what remains proposed or deferred.
Use only the relevant linked reference when further reading is necessary. Search
results are curated metadata, not evidence that every proposal was implemented.

## “Which historical experiments failed or remain incomplete?”

Run `archive experiments --status failed --json` and, when relevant,
`archive experiments --status incomplete --json`. Preserve the recorded candidate,
deployment, denominator, evidence category, costs/unknowns and resulting decision.
Do not combine passes across candidates or relabel provider/administrative failures
as numerical outcomes. This command reads history without executing an experiment.

## Setup and private handoff

Use `doctor` for local dependency/source/example diagnostics. `example options`
or `example trading` exercises the bundled synthetic workflow with a new output.
For a requested private handoff, `bundle <run-dir> --out <new.zip>` verifies saved
inputs and packages only allowed run files. State that it includes user inputs
and local paths, is private by default, and performs no upload. A public export
requires the separate curated publication workflow.
