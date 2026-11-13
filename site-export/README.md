# Generated public projection

Do not edit the JSON here directly. `scripts/export_site.py` derives `archive.json`
from the canonical research and experiment indexes and generates
`pricing-reference.json` using the Python options engine. Both are safe static
inputs for the portfolio; their hashes identify the exact exported bytes.

The archive excludes raw evidence and local paths. It retains historical source
identities and availability limitations. The pricing corpus has 64 scoped cases;
its normal-CDF approximation tolerance is specified separately from Python's
quadrature and finite-difference checks. No universal accuracy claim follows.

The canonical archive is checked byte-for-byte. Pricing references preserve exact
case inputs, identities, source hash and checker counts. Cross-platform analytic
prices may differ within `rel_tol=1e-11, abs_tol=1e-12`; every such difference is
reported, and `--check` keeps/copies the frozen file bytes. Larger drift or any
change in verification coverage fails. This tolerance is distinct from the
browser CDF approximation bound.
