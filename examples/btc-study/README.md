# Did buying BTC after a rise earn enough to cover trading costs?

Bitstamp BTC/USD, 2020–2024. Momentum meant buying when BTC closed higher than 20 days earlier.

Starting with $10,000, momentum finished at $39,414 after costs. The passive BTC/cash account finished at $70,715. It set its BTC share yearly from past signals. The evidence is inconclusive. Future performance is unmeasured.

[View equity curves](../../reports/btc-financial-v1/equity.svg) · [Read the financial report](../../reports/btc-financial-v1/README.md) · [Download the offline dashboard](dashboard.html) · [Reproduce this study](../../docs/plugin-guide.md)

Momentum made 188 trades against the passive account’s 5. Each fill paid a 0.50% fee and assumed a 0.10% worse price. Its deepest fall from a previous closing high (drawdown) was 71.82%, versus 53.52%. Its Sharpe ratio, which measures average return relative to variability, was 0.825 versus 1.166.

The price signal and the investment answer different questions. The next day’s BTC return averaged 0.207 percentage points more after a positive signal. The 95% interval spans -0.096 to +0.495 points. The interval for the net Sharpe difference spans -0.980 to +0.265. Both intervals include zero. The passive account’s advantage in this sample leaves the ranking in future periods uncertain.

![After-cost equity from the five calendar years. The passive BTC/cash line ends above the momentum line.](../../reports/btc-financial-v1/equity.svg)

The secondary FFT rule kept a positive momentum signal only when spectral entropy over the last 64 completed returns was at or below its training median. Average BTC exposure fell from 57.69% to 34.26%. After costs, plain momentum returned +294.14% and the gated rule returned +41.83%. The gated account ended at $14,183.

[Frozen specification](../../experiments/btc-financial-v1/protocol.json) · [Numerical checks](../../reports/btc-financial-v1/verification.json) · [Earlier six-month pilot](../../research/btc-pilot-audit/README.md)

Adapted from Zielak (mczielinski), *Bitcoin Historical Data*, Kaggle v706, normalized by ff137. The UTC portfolio tables and plots use [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
