# Experiment archive

[`experiments.json`](experiments.json) is the canonical curated evidence ledger. It contains seventeen historical observations or proposals, preserving failures and unknowns rather than constructing a combined score.

- `official_reported`: user reports or archived platform observations, with chronology and artifact-association limits. No score was freshly checked on the platform for this archive. `status: unknown` means whole-task success is not inferred from the aggregate.
- `local_live`: historical real-model execution, with deployment, candidate, denominator and usage kept distinct from official results.
- `synthetic`: scripted infrastructure controls, not model or market performance.
- `incomplete`: a started evaluation stopped; failed and not-run units remain in coverage.
- `not_run`: a proposal with no observations, run ID, code identity or usage fabricated.

R29's complete NVIDIA result and its official-associated aggregate are separate records. R55/R56, R58/R59 and R60/R61 are selected experiments on different candidate images and fresh responses; they are not paired causal estimates. R72 retains its STOP and 84 unrun units. R84 retains ten selected passes, an outside-scope historical provider failure and 75 unrun units. No cross-candidate pass union is reported.

The two TypeError trials are useful self-debugging negatives: the first combines a program failure with an unavailable repair response; the second executes successfully but fails numerical grading. Neither implements or validates LDB's basic-block tracing.

Every `sources` entry gives a repository-relative historical path, receipt-storage commit and SHA-256. `code_commit` separately identifies the tested solver source when known. Image manifests, OCI configurations and source fingerprints remain separately labelled. Historical source availability is not assumed; the archive contains summaries rather than private raw evidence.

Null means unknown or not executed, not zero. Monetary billing remains unknown where only calls, tokens or local provider units were recorded. The source-reproduction fields permit historical inspection, not renewed live inference. The new archive consumed no billed model, data or cloud-compute budget.
