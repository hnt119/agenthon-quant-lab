# Inspect and compare daily market prices

The v0.3.0rc1 review candidate compares a fixed moving-average strategy with buy-and-hold and cash. The bundled example uses 91 UTC dates of Bitstamp BTC/USD observations from April through June 2025. Read the resulting portfolio comparison or inspect how the minute bars were adapted into daily opens and closes. [Example report](../reports/historical-q2/report.md) · [Data source, license and extraction](../examples/data/bitstamp/README.md)

## Run the example

The review branch contains the calendar-quarter example, its saved report and the independent reference script. Use the commands below from a fresh clone. If you already have the candidate checkout, start at the setup command. `inspect-data` reads the specification and reports the data-quality summary. Check the mapped columns, date range, row count and calendar gaps before interpreting the strategy.

```sh
git clone --branch codex/v03-historical-workflow https://github.com/hnt119/agenthon-quant-lab.git
cd agenthon-quant-lab
python3 scripts/setup.py
.venv/bin/python -m agenthon_quant inspect-data examples/historical.json
.venv/bin/python -m agenthon_quant example historical --out runs/btc-q2
```

Open `runs/btc-q2/report.md` for the period tables and validation status. Open `equity-drawdown.svg` in that directory to see the equity and drawdown paths, or use `equity-drawdown.csv` for the underlying observations. `run.json` captures the assumptions, input identities, portfolio results and checks. Both fees and slippage are assumptions. The example starts with USD 10,000, uses a five-close SMA, charges 10 basis points per side in fees and applies five basis points per side of adverse slippage. [Example specification](../examples/historical.json)

April is the training period, May is validation, and June is the held-out test. Here “train” names the initial chronological period. The strategy and its parameters are fixed before evaluation. Trades use the next observed open after the signal close. Buy-and-hold enters after the same warmup and cash earns zero. Positions and cash carry across period boundaries. Daily drawdown tracks the full running peak, while each period's maximum drawdown starts from that period's opening equity. Read gross and net results alongside the benchmark and keep losing periods visible.

## Independently verify the example

A second implementation uses Python's standard library and 50-digit decimal arithmetic. It checks the fixture identity, all three portfolios, every daily equity and drawdown, and the full-period and split-period metrics. Run it against your freshly generated example or replace the run path with `reports/historical-q2/run.json` to inspect the saved result. The reference has a fixed scope of one dataset and configuration. [Reference implementation](../scripts/check_bitstamp_example.py) · [Saved comparisons](../reports/historical-q2/decimal-review.json)

```sh
python3 scripts/check_bitstamp_example.py --fixture examples/data/bitstamp/btcusd-2025-q2.csv --run runs/btc-q2/run.json
```

## Use your own daily CSV or Parquet

Copy `examples/historical.json` and set `data` relative to the copied specification. Supply `source`, `price_adjustment` (`unadjusted` or `split_adjusted`), and observed dates for `train_end` and `validation_end`. Keep positive finite open and close prices on the same basis. The test period begins on the observation after `validation_end`. Training needs at least one observation after warmup, and both subsequent periods need observations.

- **Column mapping.** The default headers are `date`, `open` and `close`. For different headers, provide a complete one-to-one map such as `"columns": {"date": "Day", "open": "OpenUSD", "close": "CloseUSD"}`. Each source column can fill only one role.
- **Session labels.** `session_date` uses `YYYY-MM-DD`. For an offset-bearing timestamp use `"timestamp_convention": "offset_timestamp"` and a named `"session_timezone"`, such as `"America/New_York"`. The importer converts each timestamp to the local civil date there. For an overnight market with different trading-date rules, supply the venue's session labels directly. Parquet also accepts native dates and timezone-aware timestamps under the matching convention.
- **Ordering and limits.** Supply one row per session, in increasing order. Invalid prices, repeated dates, reversed order and missing fields stop the import. Calendar gaps count unobserved dates between adjacent rows, including weekends and holidays. The importer does not infer an exchange calendar or fill missing prices. Limits are 10,000 rows, 256 source columns, 25 MiB per input and 25 MiB of declared uncompressed Parquet data. CSV physical lines are limited to 256 Ki characters.
- **Portfolios.** `strategies` selects from `sma`, `buy_and_hold` and `cash`. Buy-and-hold is included in each comparison. Positions are long-only and fractional. The model marks final positions at the last close and excludes dividends, cash interest, market impact, taxes and borrowing. [Accounting conventions](trading-conventions.md)

```sh
.venv/bin/python -m agenthon_quant inspect-data examples/historical.json
.venv/bin/python -m agenthon_quant run examples/historical.json --out runs/btc-custom
.venv/bin/python -m agenthon_quant verify-inputs runs/btc-custom
.venv/bin/python -m agenthon_quant reproduce runs/btc-custom --out runs/btc-repeat
.venv/bin/python -m agenthon_quant bundle runs/btc-custom --out runs/btc-private.zip
```

Replace the example specification with your own file for the first two commands. Keep the output paths fresh. Exact reproduction checks the saved inputs and requires the recorded engine fingerprint and compatible environment. Use `--set 'fee_bps=20'` with `reproduce` for a separate fee scenario. The archive includes the run's input data and provenance, so inspect its contents and the data license before sharing. For licensed Bitstamp data retain the source attribution, license link and adaptation description. [Reproduction and private bundles](user-guide.md)

A comparison over one venue and one quarter measures performance under the stated execution assumptions. Changing parameters after reading June outcomes uses the holdout in model selection. Signal timing, cost and benchmark checks validate properties of the calculation. The venue's available depth and achievable trading costs require separate evidence.
