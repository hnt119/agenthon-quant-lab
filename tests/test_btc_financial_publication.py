import csv
import json
from pathlib import Path
import unittest
from xml.etree import ElementTree

from agenthon_financial.study import ROOT


class FinancialPublicationTests(unittest.TestCase):
    def test_published_portfolio_and_stress_tables_match_the_receipt(self):
        folder=ROOT/"reports/btc-financial-v1"
        result=json.loads((folder/"metrics.json").read_text())
        markdown=(folder/"README.md").read_text()
        names={"momentum20":"Momentum","passive_mix":"Passive BTC/cash","momentum20_fft":"Momentum + FFT",
               "buy_and_hold":"Buy and hold","cash":"Cash"}
        for arm,name in names.items():
            if arm=="cash":
                continue
            m=result["portfolios"]["base"][arm]["pooled"]
            cells=[name,f'{m["total_return"]:+,.2%}',f'{m["annual_return"]:+.2%}',f'{m["sharpe"]:.3f}',
                   f'{m["annual_vol"]:.2%}',f'{m["max_drawdown"]:.2%}',f'{m["mean_close_exposure"]:.2%}',
                   f'{m["turnover"]:.2f}×',str(m["trade_events"]),f'{m["fees"]:,.0f} / {m["slippage_cost"]:,.0f}']
            self.assertIn("| "+" | ".join(cells).replace("100.00%","100%")+" |",markdown)
        for scenario,arms in result["portfolios"].items():
            cells=[f'{arms[a]["pooled"]["total_return"]:+,.2%}' for a in ("momentum20","passive_mix","momentum20_fft","buy_and_hold")]
            cells.append(f'{result["sharpe_delta"][scenario]["pooled"]:+.3f}'.replace("-","−"))
            self.assertIn(" | ".join(cells).replace("-","−")+" |",markdown)

    def test_saved_chart_and_export_cover_all_books_and_periods(self):
        p=ROOT/"reports/btc-financial-v1"
        with (p/"tables.csv").open(newline="") as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len({(r["scenario"],r["arm"],r["period"]) for r in rows}),120)
        svg=ElementTree.parse(p/"equity.svg")
        self.assertIn("Passive BTC/cash",[e.text for e in svg.iter("{http://www.w3.org/2000/svg}text")])
        html=(p/"dashboard.html").read_text()
        self.assertEqual(html.count('<svg role="img"'),6)
        self.assertIn("2024 · daily base decisions",html)
        self.assertIn("Assumptions, uncertainty and run identity",html)
        self.assertNotIn("<script",html)
