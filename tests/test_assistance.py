import unittest
from decimal import Decimal

from agenthon_quant.assistance import Budget, BudgetExceeded, Limits, MockAssistant


class AssistanceTests(unittest.TestCase):
    def test_default_stops_before_dispatch(self):
        assistant = MockAssistant(Budget(), ["not dispatched"])
        with self.assertRaises(BudgetExceeded):
            assistant.explain("request")
        self.assertEqual(assistant.budget.calls, 0)

    def test_exact_limits_and_no_retry(self):
        assistant = MockAssistant(Budget(Limits(1, 6, Decimal("0"), 10)), ["yes"])
        self.assertEqual(assistant.explain("abc", max_output_tokens=3)["text"], "yes")
        with self.assertRaises(BudgetExceeded):
            assistant.explain("abc", max_output_tokens=3)
        self.assertEqual(assistant.budget.calls, 1)

    def test_money_reserved_before_request(self):
        budget = Budget(Limits(2, 100, Decimal("0.01"), 10))
        with self.assertRaises(BudgetExceeded):
            budget.reserve(input_tokens=5, max_output_tokens=6,
                           input_dollars_per_token=Decimal("0.001"), output_dollars_per_token=Decimal("0.001"))
        self.assertEqual(budget.calls, 0)

    def test_deadline_and_failure_do_not_refund(self):
        now = [0]
        budget = Budget(Limits(2, 100, Decimal("0"), 1), clock=lambda: now[0])
        assistant = MockAssistant(budget, ["too long"])
        with self.assertRaises(ValueError):
            assistant.explain("x", max_output_tokens=1)
        self.assertEqual(budget.calls, 1)
        now[0] = 1
        with self.assertRaises(BudgetExceeded):
            assistant.explain("x")

    def test_invalid_budget(self):
        for kwargs in ({"calls": True}, {"tokens": -1}, {"seconds": float("nan")}, {"dollars": Decimal("NaN")}):
            with self.assertRaises(ValueError):
                Limits(**kwargs)
