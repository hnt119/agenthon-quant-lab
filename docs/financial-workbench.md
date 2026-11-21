# Financial research workbench

A dated input snapshot and a protocol freeze precede a historical run. An independent replay checks the saved decisions and ledgers before the existing offline dashboard can render them. The original BTC audit and the controlled-model study keep their own identities. [BTC research report](../reports/btc-financial-v1/README.md) · [Reproduction and source rights](../experiments/btc-financial-v1/README.md)

| Responsibility | Implementation |
|---|---|
| Qualify source data | [Extractor](../scripts/extract_btc_research.py) checks the pinned compressed archive and builds one UTC session per date with two delayed opening prices. [Source manifest](../experiments/btc-financial-v1/source.json) records the upstream terms and observed quality. |
| Freeze experiment inputs | [Protocol](../experiments/btc-financial-v1/protocol.json) binds the snapshot, source manifest, evaluation dates, scenarios, uncertainty and decision rule. |
| Make causal decisions and account for trades | [Study](../src/agenthon_financial/study.py) reuses [pilot signals](../src/agenthon_btc/pilot.py), the shared [spectral diagnostic](../src/agenthon_quant/spectral.py), opening fills and the [spot ledger](../src/agenthon_quant/trading.py). Its new fractional rebalance solves for the desired BTC weight after both fee and slippage. |
| Measure predictive and economic outcomes | [Analysis](../src/agenthon_financial/analysis.py) adds paired label construction and within-year block resampling to existing period accounting. |
| Independently check the financial record | [Verifier](../src/agenthon_financial/verify.py) uses direct DFTs, dated source quotes, explicit signed cash flows and post-trade weight identities. The runner also regenerates the uncertainty estimates from saved daily paths. |
| Preserve and inspect results | [Run handler](../src/agenthon_financial/run.py) records hashes, time, environment and failures. [Dashboard renderer](../src/agenthon_financial/view.py) reuses the pilot chart and Edge Lab panel format. Rendering consumes hash-checked, replayed results. [Manual logger](../src/agenthon_financial/observe.py) writes one dated signal under the frozen rules. |

## What carried over from Agenthon

The competition work established the value of a bounded action, a recorded observation and an independent numerical check. The workbench retains exact source identities, preserves failed attempts and records paid resources. Each simulated order has a dated decision, quote, balance transition and checkable resulting equity. A price series and a trade ledger can answer different questions about the same signal.

| Research mechanism | Status in this release |
|---|---|
| Interleaved observations and actions | ReAct-inspired inspection was implemented in the separate agent evaluation. BTC analysis records deterministic decisions and observations. No model selected signals or filled gaps. [Yao et al., ReAct](https://arxiv.org/abs/2210.03629) |
| External critique and bounded repair | The engineering comparison adapts tool feedback and one constrained revision. Here an independent financial verifier checks a completed run. The historical eight-case model pilot produced three exact repairs across six defects. In the later development smoke a verifier-guided revision restored a defective lot count. [Gou et al., CRITIC](https://arxiv.org/abs/2305.11738) |
| Reflection across attempts | Reflexion is documented as inspiration. The financial run uses no learned memory or iterative strategy repair. Basic-block debugging remains proposed in the research archive. [Paper-to-implementation registry](../research/papers.json) |
| Frequency-domain reasoning | FITS studies complex-frequency interpolation and FAN learns a normalization for forecasting. The implemented BTC feature summarizes the concentration of power across the trailing 64 returns. Neither forecasting architecture was reproduced. The negative gated return is recorded in both financial studies. [Xu et al., FITS](https://arxiv.org/abs/2307.03756) · [Ye et al., FAN](https://proceedings.neurips.cc/paper_files/paper/2024/hash/37c6d0bc4d2917dcbea693b18504bd87-Abstract-Conference.html) |

The separate 72-case, 24-family controlled comparison is **paused pending independent human reviews**. Its cases, packets, acceptance conditions and historical billing records remain in their original workstream.

## A possible MES replication

First qualify licensed, timestamped trades and executable quote proxies by individual contract. Document exchange sessions, holiday schedules, overnight breaks, time zones, daylight-saving transitions and the point at which each settlement was observable. Prespecify a contract selection and roll rule, identify roll trades by contract, and keep any adjusted signal series separate from actual fill and settlement prices.

Implement contract multiplier and tick rounding, integer lots, daily variation margin, collateral interest, margin requirements, commissions and two-sided roll costs. Use a capital-matched, continuously rolled passive benchmark. Independently reconcile synthetic long, expiry, roll and margin cases before authorizing any historical experiment. Venue terms, data rights, source coverage, a futures ledger and a new protocol are outstanding. This release evaluates BTC spot only.
