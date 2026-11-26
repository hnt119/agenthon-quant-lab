from unittest import TestCase

from agenthon_financial.cost_crossings import RefinementBudgetReached, crossings


class CrossingTests(TestCase):
    def solve(self, function, xs=(0, 0.5, 1), limit=12, evaluator=None):
        return crossings([(x, function(x)) for x in xs], evaluator or function,
                         zero_tolerance=1e-10, width_tolerance=0.0002, max_midpoints=limit)

    def test_multiple_sign_changes_are_refined_separately(self):
        result = self.solve(lambda x: (x - 0.18) * (x - 0.73))
        self.assertEqual(result["status"], "multiple_detected")
        for event, root in zip(result["events"], [0.18, 0.73], strict=True):
            self.assertLessEqual(event["hi"] - event["lo"], 0.0002)
            self.assertTrue(event["lo"] <= root <= event["hi"])
            self.assertLess(event["value_lo"] * event["value_hi"], 0)

    def test_absent_crossing_flat_and_endpoint_equality(self):
        result = self.solve(lambda x: 1 + x * 1e-12)
        self.assertEqual(result["status"], "no_crossing_detected")
        self.assertEqual(len(result["near_flat_intervals"]), 2)
        for root in [0, 1]:
            event, = self.solve(lambda x: x-root)["events"]
            self.assertTrue(event["boundary"])
            self.assertEqual(event["estimate"], root)
        flat, = self.solve(lambda x: 5e-11 * x)["events"]
        self.assertEqual(flat["kind"], "sampled_equal_range")
        self.assertIsNone(flat["estimate"])

    def test_missing_statistic_breaks_a_bracket(self):
        result = self.solve(lambda x: None if x == 0.5 else x-0.5)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["events"], [])
        self.assertEqual(result["undefined_samples"], [0.5])
        result = self.solve(lambda x: x-0.1, evaluator=lambda x: None)
        self.assertEqual(result["events"][0]["kind"], "undefined_refinement")

    def test_work_limits_retain_unresolved_bracket(self):
        def exhausted(_):
            raise RefinementBudgetReached()
        for result in [self.solve(lambda x: x-0.1, limit=1),
                       self.solve(lambda x: x-0.1, evaluator=exhausted)]:
            event, = result["events"]
            self.assertEqual(event["kind"], "refinement_limit")
            self.assertIsNone(event["estimate"])
            self.assertLess(event["value_lo"] * event["value_hi"], 0)

    def test_an_unsampled_touch_is_not_claimed_as_a_root(self):
        self.assertEqual(self.solve(lambda x: (x-0.2)**2)["status"], "no_crossing_detected")
