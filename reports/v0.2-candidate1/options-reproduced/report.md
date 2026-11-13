# Agenthon Quant Lab — options

**Status: passed** · v0.2.0 · 2026-11-13T17:39:34.449631+00:00

This is an offline calculation/simulation. Numerical checks do not establish predictive accuracy or trading profitability.

## Results

Prices are per unit of underlying; derivative units are specified below.

| Option | Price | Delta | Gamma | Vega | Rho | Theta/year |
|---|---:|---:|---:|---:|---:|---:|
| call | 9.2270055 | 0.58685115 | 0.018950579 | 37.901158 | 49.458109 | -5.0893189 |
| put | 6.3300806 | -0.39334753 | 0.018950579 | 37.901158 | -45.664833 | -2.2935691 |

### Volatility scenarios

| Annual volatility | Option | Price |
|---:|---|---:|
| 0.00% | call | 2.8969249 |
| 0.00% | put | 0 |
| 10.00% | call | 5.4713486 |
| 10.00% | put | 2.5744237 |
| 20.00% | call | 9.2270055 |
| 20.00% | put | 6.3300806 |
| 30.00% | call | 13.020281 |
| 30.00% | put | 10.123356 |

## Specification

```json
{
  "currency": "USD",
  "dividend_yield": 0.02,
  "maturity_years": 1.0,
  "option_type": "both",
  "rate": 0.05,
  "spot": 100.0,
  "strike": 100.0,
  "volatility": 0.2,
  "volatility_scenarios": [
    0.0,
    0.1,
    0.2,
    0.3
  ],
  "workflow": "options"
}
```

## Assumptions

```json
{
  "model": "Black-Scholes-Merton; European vanilla; one unit of underlying",
  "currency": "USD",
  "rate_compounding": "continuous",
  "dividends": "constant continuous annual yield; discrete dividends unsupported",
  "maturity": "explicit year fraction; no calendar/day-count conversion performed",
  "volatility": "annualized log-return volatility in decimal units",
  "greek_units": {
    "delta": "price per one currency-unit increase in spot",
    "gamma": "delta per one currency-unit increase in spot",
    "vega": "price per +1.0 decimal annual volatility (multiply by 0.01 for one percentage point)",
    "rho": "price per +1.0 decimal annual rate (multiply by 0.01 for one percentage point)",
    "theta": "calendar theta: -dPrice/dMaturity, per year"
  },
  "random_seed": null
}
```

## Verification

| Check | Status | Evidence |
|---|---|---|
| call_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| call_price_bounds | passed | Discounted European lower and upper bounds |
| call_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| call_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| call_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| call_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| call_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| call_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| put_price_bounds | passed | Discounted European lower and upper bounds |
| put_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| put_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| put_call_parity | passed | C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested |
| scenario_roster | passed | Scenario outputs must match the complete requested volatility list and order |
| scenario[0].input | passed | Scenario volatility equals requested decimal volatility |
| scenario[0].call_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[0].call_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[0].call_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[0].call_greek_finite_differences | unavailable | Central finite differences are not used at the expiry or zero-volatility boundary; null quantities are explicitly unavailable |
| scenario[0].call_boundary_greeks | passed | Check explicit deterministic derivatives and unavailable boundary quantities |
| scenario[0].put_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[0].put_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[0].put_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[0].put_greek_finite_differences | unavailable | Central finite differences are not used at the expiry or zero-volatility boundary; null quantities are explicitly unavailable |
| scenario[0].put_boundary_greeks | passed | Check explicit deterministic derivatives and unavailable boundary quantities |
| scenario[0].put_call_parity | passed | C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested |
| scenario[1].input | passed | Scenario volatility equals requested decimal volatility |
| scenario[1].call_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[1].call_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[1].call_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[1].call_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].call_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].call_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].call_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].call_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[1].put_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[1].put_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[1].put_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[1].put_call_parity | passed | C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested |
| scenario[2].input | passed | Scenario volatility equals requested decimal volatility |
| scenario[2].call_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[2].call_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[2].call_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[2].call_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].call_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].call_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].call_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].call_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[2].put_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[2].put_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[2].put_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[2].put_call_parity | passed | C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested |
| scenario[3].input | passed | Scenario volatility equals requested decimal volatility |
| scenario[3].call_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[3].call_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[3].call_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[3].call_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].call_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].call_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].call_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].call_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_finite_structure | passed | Finite price and exactly five finite-or-null Greek quantities required |
| scenario[3].put_price_bounds | passed | Discounted European lower and upper bounds |
| scenario[3].put_payoff_quadrature | passed | Independent discounted risk-neutral payoff integration (QUADPACK); deterministic payoff at boundary |
| scenario[3].put_delta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_gamma_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_vega_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_rho_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_theta_finite_difference | passed | Central finite differences at h and h/2 must stabilize and agree with the reported analytic derivative |
| scenario[3].put_call_parity | passed | C-P = S exp(-qT)-K exp(-rT); complementary side recomputed when only one side requested |

## Warnings and limitations

- Model values are conditional on constant volatility, rates and continuous dividend yield; numerical checks do not establish market accuracy.
- Zero-volatility prices use the deterministic discounted payoff. At its kink, non-two-sided derivatives are null; finite-difference Greek checks are unavailable.
- Some validation checks are unavailable; inspect their applicability before interpreting results.

## Provenance and reproduction

Source commit: `e97cb195dff75a5264638f62d05015bf34c4a934`; runtime source dirty: `False`.

Source fingerprint (SHA-256, distinct from Git): `f553fc7f36948aed378c7144e6dd8a47a944e15ef1d4fd8a36ab3f2d2d4edc78`.

Elapsed seconds: 0.362521. Model calls: 0. Model cost: $0. Randomness: none in the analysis engine.

Input snapshots, content hashes, package versions, full results and check details are in [run.json](run.json).

From the repository root, using the documented environment:

```sh
python -m agenthon_quant reproduce reports/v0.2/options-reproduced --out runs/reproduced-NEW
```
