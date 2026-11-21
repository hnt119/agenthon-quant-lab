"""Independent numerical and chronology checks, using synthetic inputs only."""
import cmath
import json
import math
import random
import unittest

from agenthon_quant.spectral import rolling_spectral_profiles, spectral_profile


class SpectralTests(unittest.TestCase):
    def test_known_eight_observation_sine(self):
        values = [math.sin(2 * math.pi * j / 8) for j in range(64)]
        profile = spectral_profile(values)
        self.assertEqual(profile["status"], "ok")
        self.assertAlmostEqual(profile["dominant_period_observations"], 8)
        # The periodic Hann taper gives an interior bin-centered sine three
        # nonzero positive-frequency powers in the ratio 1:4:1.
        expected = -(2 / 3 * math.log(2 / 3) + 2 / 6 * math.log(1 / 6)) / math.log(32)
        self.assertAlmostEqual(profile["spectral_entropy"], expected, places=12)
        self.assertAlmostEqual(profile["power_fraction"][7], 2 / 3, places=12)

    def test_independent_direct_dft(self):
        rng = random.Random(23)
        values = [rng.uniform(-0.04, 0.04) for _ in range(64)]
        mean = sum(values) / 64
        tapered = [(x - mean) * math.sin(math.pi * j / 64) ** 2 for j, x in enumerate(values)]
        # Slow O(n^2) reference, with no FFT call or production helper reuse.
        coefficients = [sum(x * cmath.exp(-2j * math.pi * k * j / 64)
                            for j, x in enumerate(tapered)) for k in range(1, 33)]
        powers = [abs(c) ** 2 * (1 if k == 32 else 2)
                  for k, c in enumerate(coefficients, start=1)]
        fractions = [p / sum(powers) for p in powers]
        actual = spectral_profile(values)
        for expected, observed in zip(fractions, actual["power_fraction"]):
            self.assertAlmostEqual(expected, observed, places=12)
        expected_entropy = -sum(p * math.log(p) for p in fractions if p) / math.log(32)
        self.assertAlmostEqual(expected_entropy, actual["spectral_entropy"], places=12)

    def test_nyquist_weight_is_not_doubled(self):
        values = [(-1.0) ** j for j in range(64)]
        result = spectral_profile(values)
        self.assertEqual(result["dominant_period_observations"], 2.0)
        self.assertAlmostEqual(result["power_fraction"][-1], 2 / 3, places=12)
        self.assertAlmostEqual(result["power_fraction"][-2], 1 / 3, places=12)

    def test_future_changes_and_extension_preserve_past(self):
        values = [0.01 * math.sin(j / 5) + 0.003 * math.cos(j / 3) for j in range(150)]
        original = rolling_spectral_profiles(values)
        changed = values[:100] + [0.4 + j / 1000 for j in range(50)]
        self.assertEqual(original[:100], rolling_spectral_profiles(changed)[:100])
        self.assertEqual(original[:100], rolling_spectral_profiles(values[:100]))
        self.assertEqual(original, rolling_spectral_profiles(values + [0.9, -0.5])[:150])

    def test_warmup_and_alignment(self):
        values = [math.sin(j / 4) for j in range(70)]
        result = rolling_spectral_profiles(values)
        self.assertEqual(len(result), len(values))
        self.assertTrue(all(v is None for v in result[:63]))
        self.assertEqual(result[63], spectral_profile(values[:64]))
        self.assertEqual(result[69], spectral_profile(values[6:70]))
        self.assertEqual(rolling_spectral_profiles([]), [])

    def test_constant_window_is_unavailable_not_zero_entropy(self):
        for value in (0.0, 0.01, -0.03, 1e300, 1e-300):
            result = spectral_profile([value] * 64)
            self.assertEqual(result["status"], "no_variation")
            self.assertIsNone(result["spectral_entropy"])
            self.assertIsNone(result["dominant_period_observations"])
            self.assertIsNone(result["power_fraction"])

    def test_scale_and_offset_invariance(self):
        values = [math.sin(j / 4) + math.cos(j / 7) for j in range(64)]
        reference = spectral_profile(values)
        for factor, shift in ((4, 0), (-3, 12), (1e290, 0), (1e-290, 0)):
            changed = spectral_profile([x * factor + shift for x in values])
            self.assertAlmostEqual(reference["spectral_entropy"], changed["spectral_entropy"], places=12)
            self.assertEqual(reference["dominant_period_observations"], changed["dominant_period_observations"])

    def test_reject_invalid_and_unbounded_inputs(self):
        for value in (float("nan"), float("inf"), -float("inf"), True, "0.1", None, 1j):
            with self.subTest(value=value), self.assertRaises(ValueError):
                spectral_profile([0.01] * 63 + [value])
        for size in (0, 63, 65):
            with self.assertRaises(ValueError):
                spectral_profile([0.01] * size)
        with self.assertRaises(ValueError):
            rolling_spectral_profiles([0.01] * 10_001)
        with self.assertRaises(ValueError):
            spectral_profile("1" * 64)

    def test_json_safe_output_and_bounded_entropy(self):
        rng = random.Random(77)
        profile = spectral_profile([rng.uniform(-1, 1) for _ in range(64)])
        json.dumps(profile, allow_nan=False)
        self.assertGreaterEqual(profile["spectral_entropy"], 0)
        self.assertLessEqual(profile["spectral_entropy"], 1)
        self.assertAlmostEqual(sum(profile["power_fraction"]), 1, places=14)


if __name__ == "__main__":
    unittest.main()
