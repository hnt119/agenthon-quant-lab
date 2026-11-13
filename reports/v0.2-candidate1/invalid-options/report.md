# Agenthon Quant Lab — options

**Status: invalid** · v0.2.0 · 2026-11-13T17:39:33.888215+00:00

This is an offline calculation/simulation. Numerical checks do not establish predictive accuracy or trading profitability.

## Results

```json
{}
```

## Specification

```json
{
  "workflow": "options",
  "spot": 100,
  "strike": 100,
  "maturity_years": 1,
  "volatility": -0.2,
  "rate": 0.05,
  "dividend_yield": 0,
  "currency": "USD",
  "option_type": "both"
}
```

## Assumptions

```json
{}
```

## Verification

| Check | Status | Evidence |
|---|---|---|
| input_and_execution_contract | failed | maturity_years and volatility must be nonnegative |

## Warnings and limitations

- maturity_years and volatility must be nonnegative

## Provenance and reproduction

Source commit: `e97cb195dff75a5264638f62d05015bf34c4a934`; runtime source dirty: `False`.

Source fingerprint (SHA-256, distinct from Git): `f553fc7f36948aed378c7144e6dd8a47a944e15ef1d4fd8a36ab3f2d2d4edc78`.

Elapsed seconds: 0.374715. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.

Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).

From the repository root, using the documented environment:

```sh
python -m agenthon_quant reproduce reports/v0.2/invalid-options --out runs/reproduced-NEW
```
