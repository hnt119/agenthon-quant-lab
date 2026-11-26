# Qualification and portfolio handoff

## Financial and distribution checks

Protocol freeze `78f7486cbee975600b9d7f581533595f507a64f6` preceded the first grid replay on `2dad3ac14e524c329e5d38e667a29b0af68d3119`. The [saved results](https://github.com/hnt119/agenthon-quant-lab/tree/364f042d0e056d73736f08dfb61cf3d9ff9b2bfd/reports/btc-cost-break-even-v1) contain all 41 coarse settings and 27 additional replays. Across those replays, verification reconciled 621,180 portfolio-days, 23,392 fills and 2,040 pooled or annual summaries. The original 0×, 1× and 2× decompressed ledger lines and canonical summary objects matched exactly on the reference Mac.

In a clean macOS Python 3.12.7 environment, the installed development wheel reproduced all eight original financial artifacts and all eight new cost-study artifacts byte-for-byte. The CLI ran outside the checkout without Git on its path. Run metadata records each invocation separately. The wheel and source distribution passed strict metadata and content checks, including a wheel rebuilt from the source distribution. The two wheel archives had matching qualified members and different archive hashes.

| Local build at package-input commit `9632d57cc499e41661703bfdcb7dc41dcd9f937a` | SHA-256 |
|---|---|
| Direct wheel | `52eb23cd436c4974e222f096357a93fbb5f22ab600852c50cf9cfbd968c5728f` |
| Source distribution | `149031ac59218fca149d8a5377ea4dceed894b4d5ddcfbd8ba4c96d72201a8c9` |
| Wheel rebuilt from source distribution | `c8b0abc973200889c5dd8914d94ac2c5da43bef99e2193ec3bbb9a3135d0fb8b` |

The [reproduction guide](README.md) installs the development study. The stable PyPI package is v0.3.1. To inspect a completed replay offline, run `python scripts/check_cost_study.py <output-directory>` from the review checkout. It reads the receipt and rebuilds the plotted differences and bracket histories from the saved portfolios. Use `python scripts/export_site.py --check` to verify the public copy.

## Website contract

The portfolio can link “We saw costs reverse the comparison. Where did that reversal occur?” to this study. Copy the following bytes from the reviewed toolkit branch. Use their displayed SHA-256 values to verify them before integration.

| File | SHA-256 | Use |
|---|---|---|
| `site-export/btc-cost-break-even.json` | `c9c243f2fa417243f1dcac7c6b8dd4b698163b95b0c518a47112a75994312a3f` | Display the 41 pooled differences and checked crossings for passive and buy-and-hold. |
| `site-export/programme.json` | `fe093ac8e16eadcd91f242969e4997d7091cb09423b37aac42b3cd08803a6ce5` | Three completed comparisons from two retrospective runs. Three proposed studies. |
| `reports/btc-cost-break-even-v1/crossings.svg` | `ee65c1a1e5dacabdeebab355593802797406f38faaee9ad7eb69750a89e6f20e` | Accessible figure with pooled Sharpe and terminal-wealth differences, one panel per comparator and criterion. |

In the public JSON, `curve` supplies observations in ascending cost order. `crossings` supplies the status, checked endpoint differences and estimated multiplier for each bracket. A missing event has no estimated value. Display the report’s attribution to Zielak (mczielinski) and ff137 and link CC BY-SA 4.0 for adapted financial data and figures. Distinguish the release installation from the pinned study reproduction. Preserve the existing route, anchors and reviewable episode links. Check that the text, chart and table agree for each criterion at desktop and 390/320 px, including keyboard navigation.

Two threshold estimates describe momentum against passive BTC/cash in 2020–2024. The Sharpe difference changed sign near 0.3071× and the wealth difference near 0.4781×. Against buy-and-hold the Sharpe difference crossed near 0.4066× and the wealth difference stayed negative at sampled costs. Multipliers scale **both** a 50 bp fee and 10 bp adverse slippage per fill. The finite grid and fill proxy limit the interpretation. No economic uncertainty interval was estimated. See the [report and annual results](../../reports/btc-cost-break-even-v1/README.md).
