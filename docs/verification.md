# v0.1 verification

Verified 14 November 2026 (Singapore time) from the installed source checkout.
Source commit: `ab2f62085f3c18ee97c555b8eb1bd6e400228ece`.
Runtime source fingerprint (SHA-256): `f07463aa017f4627188d9d83edc319fdfe221ba0919baf662cf5a0f7c073e397`.
The Git commit and source fingerprint identify different things.

- All 52 unit/integration tests pass on Python 3.12.7 / macOS arm64, with actual PyArrow CSV/Parquet equivalence.
- Option example: 82 checks passed, zero failed, two unavailable boundary finite-difference checks in its zero-volatility scenario.
- Trading example: 24 checks passed, zero failed, one unavailable external provenance/adjustment verification.
- Exact option reproduction matches the complete analysis object; a separate volatility change records its parent and overrides.
- Negative volatility is deliberately invalid, exits 2, retains its report and publishes no validated results.
- Adding one to both option prices evades parity but fails independent payoff integration; adding 100 to ledger cash fails reconciliation.
- Publication-write failures, malformed shapes, numerical range failures, future-data invariance and large-capital rounding have regressions.
- All four skill request paths execute through its real helper. Skill frontmatter validation, installed CLI entry point and `pip check` passed.

The complete command and artifact record is [verification.json](../reports/v0.1/verification.json).
The [release manifest](../release-manifest.json) records source inventory, committed-byte equivalence, artifact hashes and preservation checks.
No separately billed model calls, market data, cloud compute or official competition evaluation was used.

The original competition repository's status and tracked diff match their pre-task snapshots byte for byte. No remote was added, no push performed, and no competition release changed. This repository and its v0.1 tag are local.

The test suite demonstrates scoped numerical and accounting behavior, not forecasting accuracy, profitability, live-model performance or native behavior on every supported platform.
