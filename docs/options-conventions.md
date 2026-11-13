# European option workflow

`workflow: "options"` values one unit of a European vanilla call, put, or both under Black–Scholes–Merton. `examples/options.json` is a hypothetical parameter set, not a market quote. The implementation adapts the narrow scalar formula/convention ideas from the MIT-licensed Agenthon R29 `agent/quant/pricing.py`; it does not bring over task dispatch, benchmark answers, or competition validators.

## Explicit inputs

| Field | Meaning |
|---|---|
| `spot`, `strike` | Strictly positive prices in the same currency, per unit of underlying. |
| `maturity_years` | Nonnegative year fraction. The caller chooses and records any day-count calculation before calling; no dates or calendar conversions are inferred. |
| `volatility` | Nonnegative annualized log-return volatility as a decimal; `0.20` means 20%. |
| `rate` | Annual continuously compounded risk-free rate as a decimal; negative rates supported. |
| `dividend_yield` | Constant continuously compounded annual dividend yield as a decimal; zero must be explicit when no yield is assumed. |
| `currency` | Uppercase three-letter reporting label, e.g. `USD`. No currency conversion or ISO registry lookup is performed. |
| `option_type` | `call`, `put`, or `both` (default). |
| `volatility_scenarios` | Optional list, at most 100 entries, of nonnegative decimal volatilities. Order and duplicates are preserved. Each scenario receives the same checks as the base case. |

Unknown fields are rejected. American exercise, discrete dividends, cash-settlement conventions, transaction costs, volatility surfaces, calibration, and implied volatility are unsupported. These model inputs follow the European-price and continuous-yield conventions in [MathWorks' `blsprice` documentation](https://www.mathworks.com/help/finance/blsprice.html).

## Values and sensitivities

Prices are per one unit of underlying, without a contract multiplier. Both sides are computed from the same six numerical inputs. The model assumes constant parameters and a lognormal underlying; it is not a forecast. A risk-neutral discounted-payoff derivation is given in [Durham University's mathematical-finance notes](https://www.maths.dur.ac.uk/users/clare.wallace/Teaching/Old-MF-notes/22-23/the-blackscholes-formula.html).

| Greek | Reported derivative |
|---|---|
| delta | `dV/dS`, per one currency-unit change in spot |
| gamma | `d²V/dS²`, per squared currency unit |
| vega | `dV/dsigma`, per **1.0** decimal volatility; multiply by 0.01 for one percentage point |
| rho | `dV/dr`, per **1.0** decimal annual rate; multiply by 0.01 for one percentage point |
| theta | Calendar theta `-dV/dT`, per **year**; divide by 365 only when that reporting convention is desired |

These units are saved with every analysis. A change of units is not a change of price model. See also [QuantLib's Greek definitions](https://github.com/lballabio/QuantLib/blob/master/ql/pricingengines/blackcalculator.hpp).

At expiry, prices are exact intrinsic values. Delta/gamma are `null` at the strike; away from the strike they are the payoff derivatives. Vega and rho are zero. Theta is withheld (`null`) at expiry because the workflow does not define a derivative through the expiration event.

At zero volatility with positive maturity, prices are the deterministic discounted payoff. Away from the forward strike, ordinary deterministic delta, gamma, rho and theta apply and vega is zero. At the kink, Greeks are `null`: the workflow does not silently substitute one-sided sensitivities. The right-hand vega can be defined with an additional boundary convention, but is intentionally not reported as a two-sided derivative.

## Independent checks

Each check records `passed`, `failed`, or `unavailable`, along with its tolerance and observed evidence when applicable.

- Discounted price bounds: call between `max(S exp(-qT) - K exp(-rT), 0)` and `S exp(-qT)`; put between the opposite nonnegative difference and `K exp(-rT)`. Absolute tolerance is `2e-10 * max(1, discounted spot, discounted strike)`.
- Put–call parity: the residual in `C-P = S exp(-qT)-K exp(-rT)` uses the same scale tolerance. If only one side was requested, the complementary side is recomputed and this is disclosed in the check.
- Independent discounted payoff integration: [SciPy `quad` / QUADPACK](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.quad.html) integrates the risk-neutral payoff density, using no normal-CDF price formula. The Gaussian interval contains both density centres with ten-standard-deviation margins. The omitted tails are bounded by `(discounted spot + discounted strike) Phi(-10)`. The comparison tolerance is `2e-8 * max(1, discounted spot, discounted strike)` plus the numerical integration error estimate and tail bound. The QUADPACK estimate is not a rigorous proof of error; agreement is numerical evidence. For `sigma sqrt(T) > 12` this numerical check is explicitly unavailable. At zero volatility/expiry it instead checks the deterministic payoff.
- Sensitivity checks: central finite differences at `h` and `h/2` must converge and agree with each reported smooth-domain Greek. Spot steps are `S min(0.001, sigma sqrt(T) * 0.01)`, volatility steps `min(0.0001, sigma*0.01)`, rate step `0.00001`, and maturity step `min(0.0001, T*0.01)`. The absolute-plus-relative comparison tolerance is `2e-5 + 5e-4 abs(fine estimate)` (`2e-6` absolute floor for gamma). Step size, both estimates, and tolerance are retained. A perturbation within eight ULPs is unavailable; boundary Greek central differences are unavailable. Analytic derivative conventions and boundary outputs remain explicit.

Extreme parameters can exceed floating-point range and are rejected. The tolerance is scale-aware; a tiny deep-out-of-the-money price may only be validated to an absolute tolerance, not to meaningful relative precision. Numerical checks establish internal and reference consistency within this model, not suitability for a particular security.

## Verification and deliberate failures

Run `python -m unittest discover -s tests -p 'test_options.py' -v` in the installed environment. Tests cover dividend/negative-rate parity, quadrature agreement, smooth sensitivities, expiry, zero volatility, scenario ordering and corruption, missing conventions, non-finite inputs, and numerical applicability.

`verify(spec, results)` checks independently supplied values. The tests intentionally add the same amount to both prices: parity still passes, while payoff quadrature fails. A factor-of-100 vega unit error fails the finite-difference comparison. These show why a single invariant is insufficient and why failed results must be retained instead of patched into a passing report.
