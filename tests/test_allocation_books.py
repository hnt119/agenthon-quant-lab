"""Synthetic prices and small, explicit cash-flow checks for the Monday target."""
from datetime import date, timedelta
from unittest import TestCase

from agenthon_financial.allocation_books import allocation_entries
from agenthon_financial.weekly_books import weekly_entries


SCENARIOS = {"gross": [5, 0, 0], "base": [5, 50, 10], "double_cost": [5, 100, 20]}
SPEC = {"evaluation_years": [2020, 2021], "scenarios": SCENARIOS, "initial_cash": 10000.}


def market():
    start, end = date(2019, 12, 1), date(2021, 1, 5)
    quotes = {"2020-01-13": 150., "2020-01-20": 80., "2020-01-27": 95.}
    closes = {
        "2020-01-05": 110., "2020-01-12": 111., "2020-01-19": 112.,
        "2020-01-07": 240., "2020-01-14": 35., "2020-12-27": 110.,
        "2020-12-31": 140., "2021-01-01": 50.,
    }
    bars = []
    for i in range((end - start).days + 1):
        day = str(start + timedelta(days=i))
        bars.append(dict(date=day, open=100., price_5=quotes.get(day, 100.),
                         minute_5=7, close=closes.get(day, 100.)))
    return bars


def paths(bars, scenario):
    # Explicitly calculate the 20-completed-close feature on these synthetic prices.
    features = [dict(date=bar["date"], momentum20=bar["close"] / bars[i-20]["close"] - 1 if i >= 20 else None)
                for i, bar in enumerate(bars)]
    weekly = weekly_entries(bars, features, SPEC, scenario)
    target, control = allocation_entries(bars, weekly, scenario, SCENARIOS[scenario])
    return weekly, target, control


class AllocationBookTests(TestCase):
    def test_delayed_first_buy_and_post_cost_weights(self):
        for scenario, (_, fee_bps, slip_bps) in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                _, target, control = paths(market(), scenario)
                for path in (target, control):
                    self.assertTrue(all(r["cash"] == 10000. and r["shares"] == 0 for r in path[:5]))
                    self.assertTrue(all(r["decision_time"] is None for r in path[:5]))
                fee, slip = fee_bps / 10000., slip_bps / 10000.
                buy_factor = (1 + fee) * (1 + slip)
                for row, expected_btc in [(target[5], 10000. / (1 + buy_factor)),
                                          (control[5], 5000. / buy_factor)]:
                    self.assertEqual(row["signal_session"], "2020-01-05")
                    self.assertEqual(row["feature_cutoff"], "2020-01-06T00:00:00Z")
                    self.assertEqual(row["execution_time"], "2020-01-06T00:07:00Z")
                    self.assertAlmostEqual(row["quote"] * row["shares"], expected_btc)
                    self.assertAlmostEqual(row["cash"], 10000. - expected_btc * buy_factor)
                    weight = expected_btc / (row["cash"] + expected_btc)
                    if row["arm"] == "target50" or scenario == "gross":
                        self.assertAlmostEqual(weight, .5)
                    else:
                        self.assertLess(weight, .5)

    def test_rebalance_after_rise_and_fall_then_sell_on_flat_signal(self):
        _, target, control = paths(market(), "base")
        self.assertGreater(target[6]["exposure"], .5)  # Big Tuesday close move; no adjustment.
        for i, side in [(12, -1), (19, 1)]:
            row, prior = target[i], target[i-1]
            self.assertEqual(row["target_for_open"], .5)
            self.assertGreater(side * row["trade_quantity"], 0)
            self.assertAlmostEqual(row["shares"] * row["quote"], row["cash"])
            self.assertAlmostEqual(row["cash"], prior["cash"] - row["trade_quantity"] * row["fill_price"] - row["fee"])
            self.assertAlmostEqual(row["fee"], abs(row["trade_quantity"]) * row["fill_price"] * .005)
            self.assertAlmostEqual(row["slippage_cost"], abs(row["trade_quantity"]) * row["quote"] * .001)
            self.assertEqual(control[i]["trade_quantity"], 0.)
        for path in (target, control):
            sale = path[26]
            self.assertEqual(sale["date"], "2020-01-27")
            self.assertEqual(sale["target_for_open"], 0)
            self.assertLess(sale["trade_quantity"], 0.)
            self.assertEqual((sale["shares"], sale["exposure"]), (0., 0.))
            for before, after in zip(path, path[1:]):
                if date.fromisoformat(after["date"]).weekday() != 0:
                    for key in ("cash", "shares"):
                        self.assertEqual(after[key], before[key])
                    self.assertIsNone(after["target_for_open"])
                    self.assertIsNone(after["execution_time"])
                    self.assertEqual((after["fee"], after["slippage_cost"]), (0., 0.))

    def test_same_monday_quote_after_midweek_drift_has_no_fill(self):
        bars = market()
        for bar in bars:
            if bar["date"] == "2020-01-13":
                bar["price_5"] = 100.
        _, target, _ = paths(bars, "base")
        self.assertEqual(target[12]["target_for_open"], .5)
        self.assertIsNone(target[12]["execution_time"])
        self.assertEqual(target[12]["shares"], target[5]["shares"])
        self.assertEqual((target[12]["trade_quantity"], target[12]["fee"]), (0., 0.))

    def test_size_control_wealth_returns_and_turnover_include_inactive_cash(self):
        for scenario in SCENARIOS:
            full, _, control = paths(market(), scenario)
            previous_full, previous_total = 10000., 10000.
            for account, sleeve in zip(full, control, strict=True):
                self.assertAlmostEqual(sleeve["shares"], account["shares"] * .5)
                self.assertAlmostEqual(sleeve["cash"], 5000. + account["cash"] * .5)
                self.assertAlmostEqual(sleeve["equity"], 5000. + account["equity"] * .5)
                self.assertAlmostEqual(sleeve["daily_return"],
                                       .5 * previous_full / previous_total * account["daily_return"])
                self.assertAlmostEqual(sleeve["fee"], .5 * account["fee"])
                self.assertAlmostEqual(sleeve["slippage_cost"], .5 * account["slippage_cost"])
                previous_full, previous_total = account["equity"], sleeve["equity"]
            self.assertAlmostEqual(control[5]["turnover"], full[5]["turnover"] / 2)
            self.assertNotAlmostEqual(control[26]["turnover"], full[26]["turnover"] / 2)

    def test_year_boundary_and_future_data_invariance(self):
        bars = market()
        original = paths(bars, "base")
        for path in original[1:]:
            marks = {r["date"]: r for r in path}
            old, new = marks["2020-12-31"], marks["2021-01-01"]
            self.assertGreater(old["shares"], 0)
            self.assertEqual((new["cash"], new["shares"]), (old["cash"], old["shares"]))
            self.assertAlmostEqual(new["daily_return"], new["equity"] / old["equity"] - 1)
            peak = max(10000., max(r["equity"] for r in path if r["date"] <= new["date"]))
            self.assertAlmostEqual(new["drawdown"], 1 - new["equity"] / peak)
        revised = [dict(b, close=b["close"] * 2, price_5=b["price_5"] * 3)
                   if b["date"] >= "2020-01-13" else b for b in bars]
        changed = paths(revised, "base")
        for before, after in zip(original[1:], changed[1:], strict=True):
            self.assertEqual(before[:12], after[:12])
            self.assertNotEqual(before[12:], after[12:])
