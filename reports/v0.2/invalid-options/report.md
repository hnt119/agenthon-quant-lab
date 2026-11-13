# Agenthon Quant Lab — options

**Status: invalid** · v0.2.0 · 2026-11-13T17:44:20.143778+00:00

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

Source commit: `da1ad13f46b6b415d9d9309a0f01e1c8919559a8`; runtime source dirty: `False`.

Source fingerprint (SHA-256, distinct from Git): `a0d1712fa4c2a8ba2f659277437978a1418d3abafd0dbacf561f899929ec8804`.

Elapsed seconds: 0.369879. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.

Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).

From the repository root, using the documented environment:

```sh
python -m agenthon_quant reproduce reports/v0.2/invalid-options --out runs/reproduced-NEW
```
