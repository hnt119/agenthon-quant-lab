"""Boundary checks for cost sensitivity admission and original-record comparison."""
import copy
import hashlib
import json
from unittest import TestCase

from agenthon_financial.cost_books import CostBooks, _differences


class CostBooksTests(TestCase):
    def test_out_of_range_cost_fails_before_book_access(self):
        empty = CostBooks.__new__(CostBooks)
        for value in (-1, 2.1, float("nan"), float("inf"), True, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "multiplier"):
                empty.evaluate(value)

    def test_undefined_sharpe_preserves_defined_wealth_difference(self):
        portfolios = {name: {"pooled": {"sharpe": sharpe, "ending_equity": equity}}
                      for name, sharpe, equity in
                      [("momentum20", 1., 115.), ("passive_mix", None, 100.), ("buy_and_hold", .5, 120.)]}
        self.assertEqual(_differences(portfolios), {
            "passive_sharpe": None, "passive_wealth": 15., "hold_sharpe": .5, "hold_wealth": -5.})

    def test_original_row_bytes_and_summary_equivalence_are_separate(self):
        # Original raw JSONL bytes, with the row's scenario and date intact.
        raw = b'{"date":"2024-01-01","equity":10000.5,"scenario":"base"}\n'
        rows = [json.loads(raw)]
        portfolio = {"cash": {"pooled": {"ending_equity": 10000.5, "sharpe": None}}}
        books = CostBooks.__new__(CostBooks)
        books._ledger_hashes = {"base": hashlib.sha256(raw).hexdigest()}
        books._anchor_rows = {"base": rows}
        books._original_portfolios = {"base": portfolio}
        exact = books._anchor_check("base", rows, portfolio)
        self.assertEqual((exact["ledger_jsonl"], exact["canonical_summary_json"]),
                         ("byte-identical", "byte-identical"))

        perturbed = copy.deepcopy(portfolio)
        perturbed["cash"]["pooled"]["ending_equity"] += 1e-10
        close = books._anchor_check("base", rows, perturbed)
        self.assertEqual((close["ledger_jsonl"], close["canonical_summary_json"]),
                         ("byte-identical", "numerically equivalent"))
        with self.assertRaisesRegex(ValueError, "Anchor ledger"):
            books._anchor_check("base", [{**rows[0], "date": "2024-01-02"}], portfolio)
        perturbed["cash"]["pooled"]["ending_equity"] += .01
        with self.assertRaisesRegex(ValueError, "Anchor period metrics"):
            books._anchor_check("base", rows, perturbed)
