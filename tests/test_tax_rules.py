from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing oa_client only reads environment variables; it makes no requests.
from oa_client import _MOCK_SKILL


def bundled_skill():
    return next(iter(_MOCK_SKILL.values()))

import cap_gains_check
import beancount_client


class CalendarHoldingPeriodTests(unittest.TestCase):
    def test_anniversaries_and_leap_years(self):
        for acquired, sold, expected in [("2024-02-28", "2025-02-27", False),
         ("2024-02-28", "2025-02-28", False),
         ("2024-02-28", "2025-03-01", True),
         ("2023-02-28", "2024-02-28", False),
         ("2023-02-28", "2024-02-29", True),
         ("2024-02-29", "2025-02-28", False),
         ("2024-02-29", "2025-03-01", True),
         ("2024-12-31", "2025-12-31", False),
         ("2024-12-31", "2026-01-01", True)]:
            with self.subTest(acquired=acquired, sold=sold):
                result = cap_gains_check.check({"acquire_date": acquired, "sell_date": sold,
                    "holding_days": 366, "gain": 100}, bundled_skill())
                self.assertEqual(result["headline"].startswith("Long-term"), expected)

    def test_missing_or_invalid_dates_are_not_guessed(self):
        for acquired, sold in [(None, "2025-03-01"), ("bad", "2025-03-01"), ("2025-03-01", "2024-03-01")]:
            result=cap_gains_check.check({"acquire_date": acquired, "sell_date": sold, "gain": 100}, bundled_skill())
            self.assertIn("needs valid dates", result["headline"])

    def test_parser_supplies_calendar_dates(self):
        gains=beancount_client.parse(ROOT / "samples/portfolio.beancount")
        self.assertTrue(gains)
        for gain in gains:
            self.assertNotIn("needs valid dates", cap_gains_check.check(gain, bundled_skill())["headline"])
