"""Financial checks use independently chosen toy parameters, not competition data."""
import copy
import math
import unittest
from agenthon_quant.options import run, validate_spec, verify

BASE = {"workflow": "options", "spot": 100.0, "strike": 100.0,
        "maturity_years": 1.0, "volatility": 0.2, "rate": 0.05,
        "dividend_yield": 0.0, "currency": "USD", "option_type": "both"}


class OptionsTests(unittest.TestCase):
    def assertChecksPass(self, report):
        self.assertFalse([x for x in report["checks"] if x["status"] == "failed"])

    def test_reference_and_quadrature(self):
        report = run(BASE)
        # Independently documented standard BSM example (closed form evaluated
        # separately); stronger run-time checks use discounted payoff quadrature.
        self.assertAlmostEqual(report["results"]["valuations"]["call"]["price"], 10.450583572185565, places=10)
        self.assertAlmostEqual(report["results"]["valuations"]["put"]["price"], 5.573526022256971, places=10)
        self.assertChecksPass(report)
        self.assertTrue(all(x["status"] == "passed" for x in report["checks"]))

    def test_negative_rate_and_dividend_parity(self):
        for change in ({"rate": -0.03, "dividend_yield": 0.04}, {"spot": 75, "strike": 140}, {"spot": 140, "strike": 75}, {"maturity_years": 0.001}):
            report = run({**BASE, **change})
            self.assertChecksPass(report)
            parity = next(x for x in report["checks"] if x["name"] == "put_call_parity")
            self.assertEqual(parity["status"], "passed")

    def test_zero_volatility_discounted_payoff(self):
        report = run({**BASE, "volatility": 0})
        values = report["results"]["valuations"]
        self.assertAlmostEqual(values["call"]["price"], 100 - 100 * math.exp(-0.05))
        self.assertEqual(values["put"]["price"], 0)
        self.assertEqual(values["call"]["greeks"]["vega"], 0)
        self.assertChecksPass(report)
        self.assertIn("unavailable", {c["status"] for c in report["checks"]})

    def test_zero_volatility_kink_is_explicit(self):
        report = run({**BASE, "rate": 0, "volatility": 0})
        for side in report["results"]["valuations"].values():
            self.assertEqual(side["price"], 0)
            self.assertTrue(all(value is None for value in side["greeks"].values()))
        self.assertChecksPass(report)

    def test_expiry_kink_and_regular_payoff(self):
        report = run({**BASE, "maturity_years": 0})
        side = report["results"]["valuations"]["call"]
        self.assertEqual(side["price"], 0)
        self.assertIsNone(side["greeks"]["delta"])
        self.assertIsNone(side["greeks"]["gamma"])
        self.assertIsNone(side["greeks"]["theta"])
        self.assertEqual(side["greeks"]["vega"], 0)
        self.assertChecksPass(report)
        report = run({**BASE, "maturity_years": 0, "spot": 110})
        self.assertEqual(report["results"]["valuations"]["call"]["price"], 10)
        self.assertEqual(report["results"]["valuations"]["call"]["greeks"]["delta"], 1)
        self.assertEqual(report["results"]["valuations"]["put"]["greeks"]["delta"], 0)

    def test_scenarios_preserve_requested_order_and_are_checked(self):
        spec = {**BASE, "volatility_scenarios": [0.3, 0.0, 0.1]}
        report = run(spec)
        self.assertEqual([s["volatility"] for s in report["results"]["volatility_scenarios"]], [0.3, 0.0, 0.1])
        self.assertChecksPass(report)
        corrupted = copy.deepcopy(report["results"])
        corrupted["volatility_scenarios"][2]["valuations"]["put"]["price"] += 2
        self.assertTrue(any(c["status"] == "failed" and c["name"].startswith("scenario[2]") for c in verify(spec, corrupted)))

    def test_single_side(self):
        for kind in ("call", "put"):
            report = run({**BASE, "option_type": kind})
            self.assertEqual(list(report["results"]["valuations"]), [kind])
            self.assertChecksPass(report)

    def test_parity_detects_bad_price(self):
        corrupted = copy.deepcopy(run(BASE)["results"])
        corrupted["valuations"]["call"]["price"] += 1
        checks = verify(BASE, corrupted)
        self.assertEqual(next(c for c in checks if c["name"] == "put_call_parity")["status"], "failed")
        self.assertEqual(next(c for c in checks if c["name"] == "call_payoff_quadrature")["status"], "failed")

    def test_common_price_error_evades_parity_but_not_quadrature(self):
        corrupted = copy.deepcopy(run(BASE)["results"])
        for side in corrupted["valuations"].values():
            side["price"] += 0.5
        checks = verify(BASE, corrupted)
        self.assertEqual(next(c for c in checks if c["name"] == "put_call_parity")["status"], "passed")
        self.assertEqual(next(c for c in checks if c["name"] == "call_payoff_quadrature")["status"], "failed")

    def test_greek_convention_error_detected(self):
        corrupted = copy.deepcopy(run(BASE)["results"])
        corrupted["valuations"]["call"]["greeks"]["vega"] *= 0.01
        checks = verify(BASE, corrupted)
        check = next(c for c in checks if c["name"] == "call_vega_finite_difference")
        self.assertEqual(check["status"], "failed")
        self.assertTrue(check["step_convergence_passed"])

    def test_nonfinite_and_malformed_results_detected(self):
        corrupted = copy.deepcopy(run(BASE)["results"])
        corrupted["valuations"]["call"]["price"] = float("nan")
        self.assertTrue(any(c["status"] == "failed" for c in verify(BASE, corrupted)))
        self.assertTrue(any(c["status"] == "failed" for c in verify(BASE, {})))

    def test_invalid_inputs_and_unsupported_conventions(self):
        for patch in ({"spot": 0}, {"strike": -1}, {"maturity_years": -1}, {"volatility": -0.1},
                      {"rate": float("nan")}, {"dividend_yield": True}, {"spot": "100"},
                      {"dividends": [1]}, {"day_count": "ACT/365"}, {"currency": "usd"},
                      {"volatility_scenarios": [-0.1]}, {"option_type": "american"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                run({**BASE, **patch})
        without_q = dict(BASE)
        del without_q["dividend_yield"]
        with self.assertRaisesRegex(ValueError, "missing explicit"):
            run(without_q)

    def test_extreme_discount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "floating-point"):
            run({**BASE, "rate": -1000})

    def test_underflow_is_explicit(self):
        with self.assertRaisesRegex(ValueError, "underflows floating-point"):
            run({**BASE, "spot": 1e-300, "strike": 1e-300, "volatility": 1e-300, "rate": 0, "dividend_yield": 0})

    def test_invalid_valuation_structure_is_a_failed_check(self):
        for malformed in (None, [], "bad"):
            checks = verify(BASE, {"valuations": malformed})
            self.assertTrue(any(c["status"] == "failed" for c in checks))

    def test_quadrature_applicability_is_explicit(self):
        report = run({**BASE, "volatility": 13})
        quad_checks = [c for c in report["checks"] if c["name"].endswith("payoff_quadrature")]
        self.assertEqual({c["status"] for c in quad_checks}, {"unavailable"})

    def test_spec_is_not_mutated(self):
        spec = {**BASE, "volatility_scenarios": [0.1, 0.3]}
        before = copy.deepcopy(spec)
        run(spec)
        self.assertEqual(spec, before)


if __name__ == "__main__":
    unittest.main()
