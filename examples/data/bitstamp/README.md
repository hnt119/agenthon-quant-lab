# BTC/USD daily trading example

Bitstamp BTC/USD minute data, github.com/ff137/bitstamp-btcusd-minute-data. The source publisher licenses its API-collected portion from 7 January 2025 onward under **Creative Commons Attribution 4.0 International**. This daily adaptation carries the same attribution and license. Preserve this notice and indicate further changes when redistributing it. [Data license at the pinned revision](https://github.com/ff137/bitstamp-btcusd-minute-data/blob/d7156d68d85714e188a1e152818281e97c89fbe5/DATA_LICENSE) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The sample covers 1 April through 30 June 2025, the first complete calendar quarter after the publisher's January handover to its own API collection. The source file contains one-minute bars in USD per BTC. We checked continuity across all 131,040 minute labels, excluded 945 zero-volume bars, and retained the first positive-volume minute's open and the last positive-volume minute's close for each of 91 UTC dates. All 91 first and last minutes had positive volume. The result contains three renamed columns. The choice of session and venue matters for a continuously traded asset.

| Artifact | Identity |
|---|---|
| Source revision | d7156d68d85714e188a1e152818281e97c89fbe5 |
| Source Git blob | 9d45b6be5eecae94b3e2a02f6d4a8c19c0349a26 |
| Source file SHA-256 | 1d920d9cd8c2e03c8d17a2b686017dd544f1c175cd11a330d817d30b3258c6e3 |
| Derived CSV SHA-256 | 371a9692925068a85aa6541fc64675891db48d46d27fa318d558043652ec707e |

The [pinned source CSV](https://raw.githubusercontent.com/ff137/bitstamp-btcusd-minute-data/d7156d68d85714e188a1e152818281e97c89fbe5/data/updates/btcusd_bitstamp_1min_latest.csv) is about 52 MiB. Rebuild the example from a local copy with the following command from the repository root.

```sh
python3 scripts/extract_bitstamp_example.py /path/to/btcusd_bitstamp_1min_latest.csv --out /tmp/bitstamp-q2-rebuilt.csv
```

The [example specification](../../historical.json) fixes the trading assumptions. Its fee and slippage are illustrative. Minute-bar first and last prices do not establish executable depth or an exchange fee tier.
