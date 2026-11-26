"""The old receipt and the installed runtime have separate, exact code identities."""
import json
import unittest

from agenthon_financial.compatibility import qualify
from agenthon_financial.reproduce import SAVED, admitted_reference
from agenthon_financial.run import sources


class CompatibilityTests(unittest.TestCase):
    def test_accept_only_the_original_or_qualified_inventory(self):
        old = json.loads((SAVED / "run.json").read_bytes())["code_files_sha256"]
        current = sources()
        self.assertEqual(admitted_reference()["code_files_sha256"], old)
        self.assertNotEqual(current, old)
        qualify(current, current)
        altered = dict(current)
        altered["src/agenthon_quant/resources.py"] = "0" * 64
        for recorded, actual in [(old, altered), (altered, current), (altered, altered), ({}, current)]:
            with self.subTest(recorded=recorded, actual=actual), self.assertRaises(ValueError):
                qualify(recorded, actual)
