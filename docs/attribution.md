# Attribution and material boundaries

The original participant repository `agenthon-track1-agent/LICENSE` (owner-held historical source) contains the MIT license with copyright “2026 Agenthon Team 166 contributors.” Numerical/API patterns were inspected there; any adapted participant code retains that notice in [this repository's license](../LICENSE). This observation is of the local license file, not an independent authorship audit of every historical artifact.

The official `track1-coding-public` kit, revision `81e3e072f8d93ecbddc5915e38710a6cce61313c`, has a root `LICENSE` headed “Attribution-NonCommercial 4.0 International.” Its AGENTS instructions also establish the public/private benchmark firewall. Organizer tasks, data, checkers, answers and canaries are not bundled or relicensed here. Existing source dependencies were inspected to choose ordinary numerical tooling; the benchmark's full sandbox requirements are not copied into the new runtime.

The v0.1 and v0.2 hand-checkable fixtures are independently authored synthetic data. The v0.3 historical sample adapts the API-collected portion of Bitstamp BTC/USD minute data, github.com/ff137/bitstamp-btcusd-minute-data, under CC BY 4.0. The fixture notice records the exact source, extraction, changes and required credit. [Bitstamp data notice](../examples/data/bitstamp/README.md) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

User-supplied data remains subject to its own source terms; supplying a file does not establish redistribution rights.

NumPy, SciPy and PyArrow remain separately licensed dependencies installed through the package manager. No third-party library source is vendored. Research papers and historical notes are linked, not republished. Agenthon is used to describe project provenance; the new repository does not claim organizer endorsement or official competition status.

Excluded from the new repository: credentials, team claim/proof material, submission ZIPs, raw private captures, evaluator/grader/reference material, canary mappings, generated competition answers and bulk archived outputs. Historical receipts remain in the original repository. The extraction does not rewrite those receipts, change the qualified release, or authorize a submission.
