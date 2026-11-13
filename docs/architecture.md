# ADR 001 — a deterministic research engine with thin interfaces

Accepted for v0.1, 14 November 2026.

The competition repository contains useful numerical helpers and strong lessons
about contracts, provenance, verification and bounded execution. Its controller,
task dispatch, candidate snapshots and evaluator infrastructure are too coupled
to the competition to become a maintainable research runtime by relocation.
The [reuse map](reuse-map.md) records the evidence behind this decision.

Create a separate local Git repository, `agenthon-quant-lab`. Preserve the original
checkout and receipts as the historical archive. Adapt the small MIT European
pricing primitives and accounting/convention ideas; author independent fixtures
and a new simulation ledger. Do not import organizer materials or old Git history.

```text
CLI / quant-research skill / future dashboard
                   |
             records.execute
         strict specification + input snapshots
                   |
       options.run / trading.run
     deterministic calculation + independent checks
                   |
       run.json + report.md + validated-results.json
```

The numerical engine uses scalar Black–Scholes–Merton formulas and SciPy QUADPACK
for an independent risk-neutral payoff integration. Standard-library CSV and an
explicit position/cash ledger suit the small single-asset strategy; PyArrow adds
Parquet decoding. Financial units, timing, costs and applicability are explicit.
No broad finance framework is needed to support these two narrow workflows.

Every run records the request, effective specification, hashes, full results,
checks, warnings, source-file inventory/fingerprint, Git commit when available,
runtime dependencies and elapsed time. Trading inputs are snapshotted before
calculation. Existing output directories are refused. Failed runs retain their
diagnostics but have no `validated-results.json`. Unavailable checks stay distinct
from failures; a passed run can contain explicitly unavailable boundary checks.
These hashes identify local bytes; they are not signatures or attestations.

Exact reproduction requires identical engine source fingerprint and input hashes.
Dependency versions are recorded; use `requirements-verified.txt` for the tested
environment. Changed assumptions create a derived run with parent identity, not
a replacement. No random draws occur in either workflow; the synthetic-data
generator's separate seed and method are recorded with the dataset.

`assistance.py` provides a mock-only budget boundary: reserve calls, token upper
bounds and Decimal cost before dispatch, check a monotonic deadline, and retain
reservations after failure. Default allocation is zero. No live transport,
credential lookup or generated-code execution is shipped. A production adapter
would additionally need trustworthy provider token/cost bounds, timeout/cancel
enforcement and explicit paid-run authorization. Tests of a mock do not establish
that behavior. The old subprocess runner is not copied as a supposed sandbox.

The skill invokes this same engine and reads its artifacts. A later dashboard
should call these functions and render their records, keeping calculations and
verification out of its UI code. See [the next milestone](next-milestone.md).
