# Next milestone

Build a small local dashboard around the completed run format:

1. A run list with workflow, status, data provenance and source version.
2. An options form with explicit units and a volatility scenario plot.
3. A strategy view with gross/net equity, drawdown, trades and buy-and-hold.
4. An assumptions/checks drawer and a “reproduce with changes” action that creates
   a new run, preserving the original and visibly identifying the changed inputs.

Acceptance: UI requests produce the same engine results as the CLI; no UI-local
financial calculations; failed/unavailable checks stay visible; user CSV/Parquet
stays local. Start with a local single-user interface, no authentication service,
broker connectivity or hosting requirement.

After that, choose one additional workflow with a specific use case and an
independent reference. Candidate extensions are dated-cash-flow discounting or
portfolio exposure summaries. Add external data only with clear adjustment and
redistribution terms. FFT, forecasting, strategy search, training and additional
agent loops remain experiments requiring controlled comparisons and explicit
cost limits. Do not promote them from research notes into capability claims.
