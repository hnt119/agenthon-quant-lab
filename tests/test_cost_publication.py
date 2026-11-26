"""Regression checks for the independent audit of the published cost-study evidence."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from scripts.check_cost_study import check, check_curve, differences


ROOT = Path(__file__).resolve().parents[1]
SAVED = ROOT / "reports/btc-cost-break-even-v1"


class CostPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = json.loads((SAVED / "grid.json").read_bytes())
        cls.extra = json.loads((SAVED / "refinements.json").read_bytes())
        cls.records = json.loads((SAVED / "crossings.json").read_bytes())
        cls.search = json.loads((SAVED / "protocol.json").read_bytes())["search"]

    def verify_record(self, key, record):
        samples = {s["lambda"]: differences(s)[key] for s in [*self.grid, *self.extra]}
        tol = self.search["sharpe_zero_tolerance"] if key.endswith("sharpe") else self.search["wealth_zero_tolerance_usd"]
        check_curve([s["lambda"] for s in self.grid], samples, record, tol, self.search, {})

    def test_entire_archived_output_and_generated_public_exhibit(self):
        self.assertEqual(check(SAVED)["status"], "passed")

    def test_dropped_crossing_and_fabricated_outcome_fail(self):
        empty = dict(self.records["passive_sharpe"], events=[], status="no_crossing_detected")
        with self.assertRaisesRegex(ValueError, "coverage"):
            self.verify_record("passive_sharpe", empty)
        invented = dict(self.records["hold_wealth"], status="crossing_detected")
        with self.assertRaisesRegex(ValueError, "criterion status"):
            self.verify_record("hold_wealth", invented)

    def test_incorrect_refinement_values_and_root_estimates_fail(self):
        for mutate in ("trial", "endpoint", "estimate"):
            altered = deepcopy(self.records["passive_wealth"])
            event = altered["events"][0]
            if mutate == "trial":
                event["trials"][0][1] *= -1
            elif mutate == "endpoint":
                event["value_lo"] = event["value_hi"]
            else:
                event["estimate"] = event["hi"]
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.verify_record("passive_wealth", altered)

    def test_summary_difference_is_bound_to_actual_wealth(self):
        altered = deepcopy(self.grid[0])
        altered["portfolios"]["passive_mix"]["pooled"]["ending_equity"] += 1
        with self.assertRaisesRegex(ValueError, "differences derived from portfolios"):
            differences(altered)
