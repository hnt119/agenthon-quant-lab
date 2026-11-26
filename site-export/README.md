# Generated public projections

Copy checked bytes from this directory into the portfolio’s `public/agenthon-quant-lab/` directory. Edit the canonical source or generator when a projection needs to change. The website renders these files as a static article.

| Public file | Canonical inputs and use |
|---|---|
| `archive.json` | `research/papers.json` and `experiments/experiments.json` supply the curated historical and financial evidence. |
| `pricing-reference.json` | The Python options engine prices 64 cases used to verify the bounded browser calculator. |
| `programme.json` | [Six-study catalogue](../research/programme.json) supplies questions, execution states and evidence. Proposed studies have no measured outcome. |
| `btc-study.json` | The independent financial replay admits the [frozen BTC run](../reports/btc-financial-v1/run.json). The BTC exporter selects zero-, base- and double-cost summaries and actual UTC month-end paths for each portfolio. Daily maximum drawdowns include closes between chart points. |

Run the following from the toolkit checkout with its development environment active.

```sh
python scripts/export_site.py --check --site-root /path/to/portfolio
python scripts/btc_public_example.py --check && \
  cp site-export/btc-study.json /path/to/portfolio/public/agenthon-quant-lab/btc-study.json
```

The first command checks and copies the archive, pricing corpus and programme. The second checks the BTC example and projection against the saved record before copying. Keep BTC attribution and CC BY-SA 4.0 with derived portfolio data and displays. The separate Q2 2025 spot example uses CC BY 4.0. [Data notices](../DATA-NOTICES.md)

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
