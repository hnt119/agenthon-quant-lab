# Agenthon Quant Lab — options

**Status: invalid** · v0.1.0 · 2026-11-13T17:03:24.150568+00:00

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

Source commit: `ab2f62085f3c18ee97c555b8eb1bd6e400228ece`; runtime source dirty: `False`.

Source fingerprint (SHA-256, distinct from Git): `f07463aa017f4627188d9d83edc319fdfe221ba0919baf662cf5a0f7c073e397`.

Elapsed seconds: 0.362755. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.

Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).

From the repository root, using the documented environment:

```sh
python -m agenthon_quant reproduce reports/v0.1/invalid-options --out runs/reproduced-NEW
```
