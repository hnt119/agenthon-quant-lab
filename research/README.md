# Research archive

[Start with the five-year BTC research example](../examples/btc-study/README.md).


[`papers.json`](papers.json) is the canonical selected reading list: twelve primary-source records with original short summaries, relevance, limitations and decisions. Titles, authors and dates were checked against linked arXiv or proceedings metadata on 14 November 2026. Summaries use the primary abstracts; this is not a new systematic literature review or a reproduction of the papers.

| Topic | Records |
|---|---|
| Constrained workflows and repair | Agentless, AlphaCodium, CRITIC |
| Diagnostics, tool use and memory | LDB, ReAct, Reflexion |
| Relevant repository context | RepoCoder, RepoGraph, Repoformer |
| Candidate selection | CodeT |
| Spectral hypotheses | FITS, FAN |

The `year` follows the linked source's first arXiv publication or conference publication, as identified by `year_basis`; verified venue years are separate. `adaptation_status` describes the current Quant Lab relationship. Inspiration is not an implemented paper method. The earlier bounded ReAct competition variant is recorded separately from this offline research engine.

Use `experiment_ids` to follow a mechanism into the experiment registry. FITS studies interpolation in the frequency domain. FAN learns to normalize and forecast changing frequency components. The original Agenthon spectral-triage proposal remains **NOT_RUN**. The completed BTC experiment used the entropy of 64 trailing returns to decide whether to act on positive momentum. Both paper models remain untested in Quant Lab. [FITS paper](https://arxiv.org/abs/2307.03756) · [FAN paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/37c6d0bc4d2917dcbea693b18504bd87-Abstract-Conference.html) · [Experiment registry](../experiments/experiments.json)

## Follow a historical decision into the current workflow

| Archive record | Observation or proposal | How to inspect its relevance today |
|---|---|---|
| `typeerror-trial2-20260928`, linked to `critic-2023` and `ldb-2024` | All five files were produced, yet 13 of 35 trade-accounting checks failed. | Historical runs check cash, shares, execution timing and fees against the observations. Read the actual check results in `run.json`. |
| `publication-ownership-20260921`, linked to `alphacodium-2024` | One of two synthetic publication controls failed after the output was computed. | Examine the completed run record, validated results and input hashes before packaging a run. |
| `r72-full86-stop-20261027`, linked to `critic-2023` | Two attempts failed, 84 units were unrun, and a full-roster score was unavailable. | The report records unavailable source/calendar checks alongside executed checks. A saved failure can be inspected using `explain`. |
| `proposed-spectral-triage`, linked to `fits-2023` and `fan-2024` | The staged spectral comparison remains unrun. | The price example evaluates predefined daily portfolio rules. Spectral forecasting and feature selection remain separate research proposals. |
| `btc-financial-research-v1`, linked to the same papers | The entropy gate reduced BTC exposure and after-cost return in the five annual evaluation folds taken together. | Inspect the [frozen gate and fit](../experiments/btc-financial-v1/protocol.json) and the [measured outcomes](../reports/btc-financial-v1/README.md#costs-delay-and-the-negative-fft-result). |

Use an ID as a local search term, for example `archive experiments typeerror-trial2-20260928 --json` or `archive papers critic-2023 --json`. These links trace design decisions. The original diagnostic cases have different data, providers and evaluation criteria from the Bitstamp portfolio example. [Experiment records](../experiments/experiments.json) · [Historical workflow](../docs/historical-workflow.md)

The three historical notes are represented by source paths and hashes in `source_notes`. They remain in the original local repository. PDFs, full paper text, competition solutions, grader material and raw captures are not copied. The shortlist is intentionally selective; omission does not imply that an unreviewed proposal was false or tested.
