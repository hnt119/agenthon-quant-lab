# From competition agent to research toolkit

The original Agenthon agent was a program-producing solver. Quant Lab is a
maintained calculation engine. The [reuse map](reuse-map.md) and canonical
[experiment ledger](../experiments/experiments.json) preserve their relationship
without making the old competition environment a runtime dependency.

## Evolution and evidence

| Stage | Mechanism and evidence | What carries forward |
|---|---|---|
| Initial contract pipeline | Task reading, bounded previews, generated execution, validation and one bounded repair; source identity in the v0.1 audit | Explicit inputs, finite values and stage-specific failures |
| Output publication | Synthetic ownership control found that correct files could fail to publish on a writable mount | Publish final completion only after artifacts succeed; preserve failed runs |
| Truncation and transport work | Usage/finish metadata and redirect refusal were added; the three-task recovery pilot never exercised truncation | Diagnose the mechanism actually exercised; synthetic contracts and live outcomes stay separate |
| Bounded ReAct variant | Inspection, generation, execution, checks and repair within a small call/time budget; historical submission recorded separately | Tool access is useful only within explicit boundaries; a more elaborate loop is not automatically better |
| R29 deterministic helpers | Narrow quantitative primitives and complete public-roster local evidence on one frozen image | Reuse the small MIT option core; independent checks and full denominators |
| Selected repairs and later providers | Caller/units/direction fixes, numerical failures, provider errors, selected passes and STOP records | Keep source, model deployment, budget and output identity attached to every claim |
| Quant Lab | Shared deterministic Python engine, authored fixtures, source/input hashes and readable reports | CLI and skill share calculations; the static website presents a sanitized projection |

These are mechanisms and historical observations, not causal paper reproductions.
Paper relationships and unknowns are explicit in the [research index](../research/papers.json).

## Boundaries that matter

**Contracts and context.** Select only participant-visible inputs and make output
shape, units, conventions and supported cases explicit. A bounded text preview
is not filesystem isolation. Hidden checks, references and canaries do not belong
in solver feedback or reusable knowledge. Current Quant Lab inputs are structured
specifications and user-owned data; no benchmark runtime is imported.

**Execution.** The old subprocess runner supplied a fresh directory, small
environment, timeout and bounded logs. The external restricted Docker environment
provided the security boundary; the subprocess alone was not a sandbox. No
arbitrary generated-code execution ships in Quant Lab. Adding it would require
verified isolation, read-only inputs, fresh attempts, resource limits and controlled
publication. There is no unrestricted fallback.

**Verification and repair.** Execution success and valid JSON are insufficient.
Parity can miss equal errors in call and put prices; independently integrated
payoffs catch them. Trading checks reconstruct cash, shares, costs and P&L. The
historical TypeError trials show that a repaired program can execute yet fail
numerically. Failures remain in the record, rather than being rewritten into a pass.

**Candidate selection.** A whole-roster result belongs to one exact source/image
and deployment. R72 retains its unrun units after STOP; selected R84 passes cannot
fill its missing denominator. Git commits, source fingerprints, OCI configs,
image manifests and ZIP hashes identify different objects. The archive preserves
these distinctions and never joins passes across candidates.

**Models and cost.** House-injected access, NVIDIA service calls and Cloudflare
runs are different deployments even if model names resemble one another. Recorded
tokens and local provider-unit estimates do not establish billed cost. Quant Lab
uses no model for its calculations. Its mock assistance boundary reserves call,
token and cost limits before dispatch; live transport remains unimplemented.

**Spectral research.** FITS and FAN motivate a possible compact time-series
summary, not a trading strategy or demonstrated Agenthon gain. The NOT_RUN protocol
compares ordinary statistics, global FFT and rolling FFT under fixed chronology,
inputs and budgets. The current release does not implement those forecasting models.

## Source trail

The original participant checkout was audited at
`a8aa309a413f3f7fe276bad4f3e05d5d9dd62a54`. R29's exact solver source is
`24827ce99d6bca1874a26b6c6cbf985d1689801e`. The [source audit](source-audit.json)
records selected file hashes; each imported experiment separately records its
receipt-storage commit and tested code identity when known. The original archive
remains unchanged and is not redistributed wholesale.
