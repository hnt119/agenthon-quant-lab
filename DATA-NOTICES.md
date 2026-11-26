# Material included with Agenthon Quant Lab

The Python software and authored synthetic example use the MIT license in LICENSE.
The following two data collections and their adaptations have separate terms.

* **2017–2024 study.** Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle version 706, normalized by ff137. The bundled Bitstamp BTC/USD extract selects complete UTC years, excludes zero-volume minutes from trade proxies, and aggregates daily closes and delayed prices. The derived portfolio ledgers, tables, figure and data-derived reports are distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Preserve the credit, license and change notice when distributing adaptations. [Original dataset](https://www.kaggle.com/datasets/mczielinski/bitcoin-historical-data) · [Pinned publisher terms](https://github.com/ff137/bitstamp-btcusd-minute-data/blob/d7156d68d85714e188a1e152818281e97c89fbe5/DATA_LICENSE)
* **Q2 2025 historical example.** Bitstamp BTC/USD minute data, github.com/ff137/bitstamp-btcusd-minute-data. The example aggregates positive-volume minutes into daily open and close prices from the API-collected portion under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The bundled examples/data/bitstamp/README.md records attribution, transformations and hashes.

Paper entries are original summaries and links. NumPy, SciPy and the optional PyArrow dependency are separately distributed.
