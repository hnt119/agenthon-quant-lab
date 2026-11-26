"""Synthetic prospective BTC books, no external data or clock."""
import copy
from datetime import date, timedelta
import unittest

from observations.paper_accounts import (
    FEE, SLIP, apply_fill, decision, fresh_accounts, mark_accounts, summarize, verify_fill,
)


def inputs(monday, direction):
    day = date.fromisoformat(monday) - timedelta(days=21)
    return [dict(date=(day + timedelta(days=i)).isoformat(), close=100 + i * direction)
            for i in range(21)]


class PaperAccountsTests(unittest.TestCase):
    def test_decision_has_no_quote_and_requires_all_completed_closes(self):
        monday = "2031-01-06"
        bars = inputs(monday, 1)
        result = decision(monday, bars)
        self.assertEqual((result["signal_date"], result["reference_date"]), ("2031-01-05", "2030-12-16"))
        self.assertAlmostEqual(result["momentum20"], .20)
        self.assertTrue(result["positive"])
        for direction in (-1, 0):
            self.assertFalse(decision(monday, inputs(monday, direction))["positive"])
        for bad in (bars[:20], bars[:10]+bars[11:]+[bars[-1]], bars[1:]+[dict(date=monday, close=123)],
                    [*bars[:7], {**bars[7], "close": False}, *bars[8:]]):
            with self.assertRaises(ValueError):
                decision(monday, bad)
        with self.assertRaises(ValueError):
            decision("2031-01-07", bars)
        after_cutoff = {"date": monday, "close": 1}
        for tomorrow in (2, 1_000_000):
            history = bars + [{**after_cutoff, "close": tomorrow}]
            self.assertEqual(decision(monday, history[:-1]), result)

    def test_first_buy_zero_interest_cash_reserve_and_exact_weight_difference(self):
        before = fresh_accounts()
        for q in (15, 133):
            self.assertEqual(mark_accounts(before, q), {"target50": 10_000., "half_funded": 10_000.})
        waiting, no_trades = apply_fill(before, False, 111)
        self.assertEqual(before, fresh_accounts())
        self.assertEqual(no_trades["target50"]["quantity"], 0)
        self.assertIsNone(waiting["half_funded"]["first_fill_weight"])
        held, trades = apply_fill(waiting, True, 100)
        factor = (1 + FEE) * (1 + SLIP)
        expected = {"target50": 10_000 / (100 * (1 + factor)),
                    "half_funded": 5_000 / (100 * factor)}
        for arm, shares in expected.items():
            with self.subTest(arm=arm):
                trade = trades[arm]
                self.assertAlmostEqual(trade["quantity"], shares)
                self.assertAlmostEqual(held[arm]["cash"], 10_000 - shares * 100 * factor)
                self.assertAlmostEqual(trade["fee"], shares * 100 * (1 + SLIP) * FEE)
                self.assertAlmostEqual(trade["slippage"], shares * 100 * SLIP)
        self.assertAlmostEqual(held["target50"]["first_fill_weight"], .5)
        self.assertAlmostEqual(held["half_funded"]["first_fill_weight"], 1/(1+factor))
        self.assertLess(held["half_funded"]["first_fill_weight"], .5)
        self.assertEqual(held["half_funded"]["cash"], 5_000.)

    def test_rebalance_both_sides_repeat_quote_and_final_exit(self):
        accounts, _ = apply_fill(fresh_accounts(), True, 100)
        first = accounts["target50"]["first_fill_weight"]
        for quote, side in ((200, -1), (50, 1), (50, 0)):
            held, trades = apply_fill(accounts, True, quote)
            self.assertEqual(trades["half_funded"]["quantity"], 0.)
            target = held["target50"]
            qty = trades["target50"]["quantity"]
            self.assertEqual((qty > 0) - (qty < 0), side)
            self.assertAlmostEqual(mark_accounts(held, quote)["target50"] / 2, target["shares"] * quote)
            self.assertAlmostEqual(target["first_fill_weight"], first)
            self.assertEqual(trades["target50"]["fee"] > 0, bool(side))
            self.assertEqual(trades["target50"]["slippage"] > 0, bool(side))
            accounts = held
        flat, sells = apply_fill(accounts, False, 300)
        for arm, row in flat.items():
            self.assertEqual(sells[arm]["quantity"], -accounts[arm]["shares"])
            self.assertAlmostEqual(row["cash"], accounts[arm]["cash"] +
                                   accounts[arm]["shares"] * 300 * (1-SLIP) * (1-FEE))
            self.assertEqual(row["shares"], 0.)
        self.assertEqual(flat["target50"]["fill_count"], 4)
        self.assertEqual(flat["half_funded"]["fill_count"], 2)

    def test_reserve_identity_and_return_across_multiple_mondays(self):
        active_cash, units = 10_000., 0.
        previous_control = previous_full = 10_000.
        accounts = fresh_accounts()
        for positive, quote, close in ((True, 70, 100), (True, 133, 170), (False, 91, 55),
                                       (False, 68, 68), (True, 28, 49)):
            accounts, _ = apply_fill(accounts, positive, quote)
            if positive and not units:
                units = active_cash / (quote*(1+SLIP)*(1+FEE))
                active_cash = 0.
            if not positive and units:
                active_cash = units * quote*(1-SLIP)*(1-FEE)
                units = 0.
            full = active_cash + units * close
            control = mark_accounts(accounts, close)["half_funded"]
            self.assertAlmostEqual(control, 5_000 + full/2)
            self.assertAlmostEqual(control/previous_control-1,
                                   (previous_full/2)/previous_control*(full/previous_full-1))
            previous_control, previous_full = control, full

    def test_year_boundary_mark_and_drawdown_use_total_wealth(self):
        accounts, _ = apply_fill(fresh_accounts(), True, 100)
        saved = copy.deepcopy(accounts)
        marks = {}
        for day, close in (("2030-12-31", 400), ("2031-01-01", 20), ("2031-01-02", 60)):
            marks[day] = mark_accounts(accounts, close)
        self.assertEqual(saved, accounts)
        result = summarize(accounts, marks, "2030-12-31", "2031-01-02")
        self.assertEqual((result["status"],result["observed_marks"]), ("complete",3))
        dds = {}
        for arm in accounts:
            dds[arm] = 1 - marks["2031-01-01"][arm] / marks["2030-12-31"][arm]
            self.assertAlmostEqual(result["accounts"][arm]["max_drawdown"], dds[arm])
            self.assertEqual(result["accounts"][arm]["ending_wealth"], marks["2031-01-02"][arm])
        self.assertAlmostEqual(result["primary_drawdown_difference_pp"],
                               100*(dds["half_funded"]-dds["target50"]))

    def test_missing_marks_never_count_as_flat_or_as_complete(self):
        books = fresh_accounts()
        start, mid, end = "2030-01-01", "2030-01-02", "2030-01-03"
        marked = mark_accounts(books, 110)
        for marks, status, counts in (({}, "collecting",(0,0,3)), ({start: None}, "incomplete",(0,1,2)),
                                      ({start:marked}, "collecting",(1,0,2)),
                                      ({start:marked,end:marked}, "incomplete",(2,1,0)),
                                      ({start:marked,mid:marked,end:None}, "incomplete",(2,1,0))):
            result = summarize(books, marks, start, end)
            self.assertIsNone(result["primary_drawdown_difference_pp"])
            self.assertIsNone(result["accounts"]["half_funded"]["max_drawdown"])
            self.assertEqual(result["status"], status)
            self.assertEqual(tuple(result[k] for k in ("observed_marks","missing_marks","pending_marks")),
                             counts)
        for bad in ({"2030-01-04":marked}, {start:{**marked,"target50":float("nan")}}):
            with self.assertRaises(ValueError):
                summarize(books, bad, start, end)
        with self.assertRaises(ValueError):
            mark_accounts(books, float("nan"))

    def test_replay_rejects_ledger_corruption(self):
        before = fresh_accounts()
        after, trades = apply_fill(before, True, 100)
        for arm, field, value in (("half_funded","reserve",4999.),("target50","cash",100.),
                                  ("target50","first_fill_weight",.499),
                                  ("half_funded","shares",True),("target50","fill_count",3)):
            damaged = copy.deepcopy(after)
            damaged[arm][field] = value
            with self.assertRaises(ValueError):
                verify_fill(before, True, 100, damaged, trades)
        for field, value in (("quantity",0.),("slippage",0.),("fill_price",None),("post_quote_weight",.6)):
            damaged = copy.deepcopy(trades)
            damaged["target50"][field] = value
            with self.assertRaises(ValueError):
                verify_fill(before, True, 100, after, damaged)
