# Reproduce the BTC momentum comparison

The admitted snapshot covers Bitstamp BTC/USD spot from January 1, 2017 through December 31, 2024. The first three years supplied the initial fit. Five subsequent years supplied retrospective evaluation. The repository contains everything needed to reproduce the financial results offline after Python setup. [Main report](../../reports/btc-financial-v1/README.md) · [Frozen protocol](protocol.json) · [Source and usage terms](source.json)

## Reproduce from the published package

From a fresh Python 3.12+ environment and a writable directory, run:

```sh
python -m pip install agenthon-quant-lab==0.5.0
quant-lab doctor
quant-lab btc-study --out btc-study
```

Start with `btc-study/report.md`, open `btc-study/dashboard.html` and check `btc-study/reproduction.json`. The release also includes the [cost](../btc-cost-break-even-v1/README.md) and [weekly decision](../btc-weekly-cadence-v1/README.md) follow-ups.

## Run from the repository root

The verified environment uses Python 3.12. A fresh checkout can install the numerical dependencies with `python3.12 scripts/setup.py`. Run the following from the checkout.

```sh
.venv/bin/python scripts/btc_financial.py verify reports/btc-financial-v1
.venv/bin/quant-lab btc-study --out runs/btc-financial-replay
open runs/btc-financial-replay/dashboard.html
```

Choose a fresh output directory for each run. The first command checks identities, reconstructs the financial paths from the admitted quotes and independently checks the financial summaries. It also repeats the frozen resampling calculation. The second regenerates the principal tables, figure, dashboard and receipts. In another operating system, open `dashboard.html` in a browser. For an existing offline Edge Lab page use `dashboard reports/btc-financial-v1 --edge path/to/dashboard.html --out path/to/new-page.html` after the script name. The output must be a new sibling of the original.

| Artifact | What it records |
|---|---|
| `sessions.csv`, `source.json` | Pinned upstream archive, license, qualified UTC rows and delayed quotes |
| `features.jsonl`, `fit.json` | Each close decision, training membership, entropy median and annual passive weights |
| `predictions.json` | Matched dates, states, entry and exit prices, forward returns for both delays |
| `ledger.jsonl.gz` | Each signal cutoff, decision, intended target, execution proxy, actual simulated fill time, cash, units, costs and closing mark. A null passive target means retain the existing units |
| `metrics.json`, `tables.csv` | All five books, four scenarios and six reporting periods, with prediction, uncertainty and decision in JSON |
| `run.json`, `verification.json` | File hashes, code identity, dependency versions, execution time, resource use and verification coverage |

The ledger is newline-delimited JSON compressed with gzip. `gzip -dc reports/btc-financial-v1/ledger.jsonl.gz | head -n 1` displays one record. Code and admitted input identities determine the numerical results. New run timestamps and the current checkout identity distinguish reproductions. Use dependencies recorded in the receipt for byte comparisons.

## Rebuild the session snapshot if desired

Download the pinned archive from the `url` in [source.json](source.json) to a local file. It is about 94 MB. The extractor verifies the complete upstream SHA-256 before it processes the selected dates. It rejects unordered minutes, duplicates, inconsistent prices, insufficient coverage and missing delayed quotes.

```sh
.venv/bin/python scripts/extract_btc_research.py /path/to/archive.csv.gz --out /tmp/bitstamp-2017-2024.csv
cmp /tmp/bitstamp-2017-2024.csv experiments/btc-financial-v1/sessions.csv
```

The source uses minute-start Unix timestamps, USD per BTC prices and BTC volume. A session begins at midnight UTC. `open` and `close` use the first and last trade-bearing candle. For each delay, `minute_5` or `minute_30` records the actual minute index and the corresponding `price_*` its open. `close_minute` locates the final trade-bearing candle. `positive_minutes` and `volume_btc` summarize trading observations. Timestamp resolution ends at the candle, so the exact first trade time within it is unknown.

## Record one observation manually

```sh
.venv/bin/python scripts/btc_financial.py observe --out /tmp/btc-observation-example.json
```

The bundled data produce a retrospective backfill. To record a new signal, supply `--snapshot /path/to/sessions.csv --source /path/to/source.json` along with a fresh output filename. First qualify any appended data under the same Bitstamp spot, UTC, positive-volume and delayed-price conventions, including permissions, gaps, duplicates and completed sessions. Retain the original snapshot bytes as a prefix, document the new source version, attribution, URL, license and acquisition timestamp, set the complete session count in `quality.days`, and bind the extended snapshot SHA-256 in `quality.sha256`. The logger checks source identity and continuity. Source licensing and acquisition quality require the collector's review.

The clock comes from the local invocation. To count as a prospective intent the completed session and protocol freeze must precede logging, and logging must occur before 00:05 UTC. The narrow window is deliberate even if the first actual trade comes later. There is no order placement or inferred outcome. Measuring future performance requires separately recorded, timestamped subsequent observations.

## Attribution and redistribution

The historical bulk originates in *Bitcoin Historical Data* by Zielak (mczielinski), Kaggle v706, normalized by ff137. The historical measurement files, tables, chart and dashboard are adaptations under CC BY-SA 4.0. Changes include selecting dates, discarding zero-volume candles from trade proxies, daily aggregation and calculating simulated financial paths. Preserve attribution, the license link and change notice when sharing adaptations. The project software uses its existing MIT license. The later API-collected segment used in the older pilot has separate terms. [Original dataset](https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data) · [Pinned publisher terms](https://github.com/ff137/bitstamp-btcusd-minute-data/blob/d7156d68d85714e188a1e152818281e97c89fbe5/DATA_LICENSE) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
