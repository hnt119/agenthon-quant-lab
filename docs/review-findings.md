# Independent review notes

Reviewed 14 November 2026. This is an implementation review of the new research package, not an Agenthon evaluation. The initial 26-test suite passed. Additional probes below exercised boundary inputs and failure paths rather than restating implementation formulas. The implementation was changing concurrently; final verification must record which findings are resolved.

| Probe | Initial observation | Required behavior / disposition |
|---|---|---|
| Options with spot = strike = `1e-300`, volatility = `1e-300`, maturity = 1, rate = yield = 0 | Division underflow raised `ZeroDivisionError`, leaving no run record. | Unsupported numerical ranges should produce an inspectable invalid run. `records.py` was subsequently observed catching `ArithmeticError`; verify final options boundary handling and report persistence. |
| `options.verify(spec, {"valuations": null})`, also list/string values | Raised `AttributeError` rather than structured failed checks. | Reject malformed outer valuation shapes explicitly. |
| `trading.verify_ledger([None], valid_one_row_quotes, 100)` | Raised `AttributeError` at `.values()`; list/integer entries behaved similarly. | Reject malformed ledger-row shapes through a failed `ledger_shape_and_quotes` check. |
| Inject write failure for `validated-results.json` only | Earlier `run.json` and report said passed, but validated output was absent and execution raised `OSError`. | Final completion metadata must follow successful artifact publication; record publication failure where possible. |

Two scope notes were passed to the integrator: source fingerprints include repository-relative paths and `pyproject.toml`, so editable-checkout and wheel installations currently have different fingerprints; document the supported reproduction path unless normalized portability is added. Also, a billion-unit initial portfolio can leave a negative `1.1920928955078125e-7` cash residual after a mathematically all-cash purchase; the absolute `1e-7` constraint can reject floating-point roundoff at that scale. This does not affect the standard 10,000-unit fixture, but numerical scope should be clear.

No source edits were made by the reviewer. Tests and probes used local temporary directories and no model calls, network services or official evaluation material.


## Final dispositions — 14 November 2026

The final reviewed runtime source fingerprint is `5df2006ebdb2594bd73ad26348b8af02b9bd790651fff60a6a41fc82ffbe81f3` (SHA-256 of the runtime source inventory, distinct from a Git commit). No commit identity is asserted by this review.

- **Resolved: underflow failure records.** The option pricer rejects an underflowed gamma denominator explicitly, and the run layer catches arithmetic errors. The regression confirms an invalid record and report are saved without validated results.
- **Resolved: malformed verifier inputs.** Option valuation mappings and trading ledger containers/rows are shape-checked and produce failed checks instead of AttributeError.
- **Resolved: publication completion.** Validated outputs and the readable report are written before the final run record. JSON writes use temporary files and replacement. A recoverable publication error removes validated output and records failed publication. Independent one-time failures at both validated-results.json and the final run.json write produced failed records and no validated output. If storage remains unwritable, a completed run marker cannot be guaranteed; consumers must require run.json rather than infer completion from partial files.
- **Resolved: large-portfolio roundoff.** All-cash buy rounding is limited to a few representable arithmetic units. Independent reconciliation uses operation-scale roundoff allowances, while injected monetary discrepancies remain detectable. The regressions cover initial capital from 1e9 through 1e14, corrupted cash/P&L, and finite inputs producing an overflowing return.
- **Documented scope: reproduction environment.** Source-checkout identity remains intentional; use the documented editable checkout and recorded dependency versions. Cross-layout wheel/source fingerprint equivalence is not claimed.

Final verification: `PYTHONPATH=src /private/tmp/agenthon-quant-lab-venv/bin/python -m unittest discover -s tests -v` passed **52 tests**, including the publication regression, hand reconciliation, independent numerical checks, temporal causality and CSV/Parquet equivalence. The two additional publication-failure probes above also passed. No material blocker remains within the reviewed v0.1 offline scope. This is not a security audit or evidence of real-model behavior, predictive accuracy or profitability.

Final source freeze: `ab2f62085f3c18ee97c555b8eb1bd6e400228ece`. After review, derived-run parent metadata was moved into the initial record before publication, and the minimum Python version was aligned with the verified dependencies (3.12). The focused record suite and final 52-test qualification passed. Final fingerprint and evidence are recorded in `release-manifest.json`.
