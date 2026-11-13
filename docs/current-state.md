# Current state — v0.1

Prepared 14 November 2026 (Asia/Singapore). This is the new standalone research
repository, not an Agenthon submission candidate. Local release identity and
final verification are recorded in `release-manifest.json` after source freeze.

Implemented: the shared engine, strict specs and snapshotted inputs, European
option pricing/scenarios/Greeks, SMA strategy and benchmark accounting, CLI,
run/reproduce/explain commands, reusable skill, source audit, lessons, synthetic
data, independent numerical/accounting regressions and a release verifier.

The code lives in `src/agenthon_quant`; examples and data in `examples`; numerical,
record and budget regressions in `tests`; reusable operations in `scripts` and
`skills/quant-research`. Source reuse and limitations are indexed in `docs`.
The original competition checkout is preserved separately.

The initial implementation suite passes 52 tests, including actual CSV/Parquet
equivalence. Final committed-source outputs are in `reports/v0.1/`.
No billed model calls, market-data purchases, cloud compute, official evaluation,
push, image publication, deployment or submission occurs in this milestone.

Known limits: two narrow workflows only; synthetic data establishes no market
edge; input source/adjustment declarations are unverified; live model behavior is
untested; generated-code execution is absent; no dashboard or live trading.
Numerical range/applicability failures remain explicit. Reproduction is supported
from a source checkout with recorded dependency versions, not across arbitrary
wheel layouts or environments.

Next action: use the README's commands on a user-owned price file with explicit
adjustment conventions, or build the small local dashboard described in
`next-milestone.md` using the same engine and saved-run format.

## Final local freeze

Source commit: `ab2f62085f3c18ee97c555b8eb1bd6e400228ece`. Final qualification: **52 tests passed**; reports and complete hashes are in [release-manifest.json](../release-manifest.json).
The installed repository is `/Users/hunt/Desktop/agenthon-quant-lab` and the discoverable skill links to its maintained source.
[Verification details](verification.md) distinguish passed, invalid and unavailable checks. The Git tag `v0.1.0` names the separate evidence commit.
