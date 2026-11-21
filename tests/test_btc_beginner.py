import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from agenthon_financial import reproduce
from agenthon_financial.reader import projection
from agenthon_financial.study import ROOT


class BeginnerStudyTests(TestCase):
    def test_missing_snapshot_explains_recovery(self):
        with TemporaryDirectory() as tmp, patch.object(reproduce,"DATA",Path(tmp)):
            with self.assertRaisesRegex(ValueError,"Restore a complete checkout"):
                reproduce.reproduce(Path(tmp)/"output")

    def test_occupied_destination_is_untouched(self):
        with TemporaryDirectory() as tmp:
            marker=Path(tmp)/"mine"
            marker.write_text("retain")
            with self.assertRaisesRegex(ValueError,"already exists"):
                reproduce.reproduce(tmp)
            self.assertEqual(marker.read_text(),"retain")

    def test_comparison_keeps_decisions_types_and_nulls(self):
        self.assertTrue(reproduce.compare({"cash": 1.00000000000001}, {"cash": 1.0}))
        for a,b in ((False,0),(None,0.),(1,2),("2024","2025"),(1.,1.001),([1],[1,2])):
            self.assertFalse(reproduce.compare(a,b))

    def test_projection_is_traceable_and_cash_sharpe_undefined(self):
        root=ROOT/"reports/btc-financial-v1"
        metrics=json.loads((root/"metrics.json").read_bytes())
        summary=json.loads((ROOT/"site-export/btc-study.json").read_bytes())
        self.assertIsNone(summary["portfolios"]["cash"]["sharpe"])
        self.assertEqual(summary["interval95"],metrics["interval95"])
        self.assertEqual(summary["month_ends"][-1]["date"],"2024-12-31")
        self.assertEqual(len(summary["month_ends"]),60)
        for arm in ("momentum20","passive_mix"):
            self.assertEqual(summary["month_ends"][-1][arm]["equity"],metrics["portfolios"]["base"][arm]["pooled"]["ending_equity"])
