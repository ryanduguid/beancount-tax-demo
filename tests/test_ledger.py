import copy
import os
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal, localcontext

os.environ["OA_MCP_TOKEN"] = ""
os.environ["OA_MCP_URL"] = "https://example.invalid"

import beancount_client
import cap_gains_check
from oa_client import OAClient

OPEN = '''2021-01-01 open Assets:Brokerage
2021-01-01 open Assets:Other
2021-01-01 open Assets:Cash
2021-01-01 open Income:Gains
'''
BUY = '''2023-01-01 * "Buy"
  Assets:Brokerage 1 ABC {10 USD}
  Assets:Cash -10 USD
'''
SELL = '''2025-01-02 * "Sell"
  Assets:Brokerage -1 ABC {10 USD} @ 30 USD
  Assets:Cash 30 USD
  Income:Gains -20 USD
'''


class LedgerTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.beancount"
            path.write_text(text, encoding="utf-8")
            return beancount_client.parse(str(path))

    def test_fifo_across_lots_preserves_remaining_quantity(self):
        ledger = OPEN + '''2023-01-01 * "First buy"
  Assets:Brokerage 2 ABC {10 USD}
  Assets:Cash -20 USD
2023-01-02 * "Second buy"
  Assets:Brokerage 3 ABC {20 USD}
  Assets:Cash -60 USD
2025-01-01 * "Partial sale"
  Assets:Brokerage -4 ABC {} @ 30 USD
  Assets:Cash 120 USD
  Income:Gains -60 USD
2025-01-02 * "Remainder"
  Assets:Brokerage -1 ABC {} @ 30 USD
  Assets:Cash 30 USD
  Income:Gains -10 USD
'''
        gains = self.parse(ledger)
        self.assertEqual([row["units"] for row in gains], [Decimal(2), Decimal(2), Decimal(1)])
        self.assertEqual([row["cost_basis"] for row in gains], [Decimal(20), Decimal(40), Decimal(20)])
        self.assertEqual([row["gain"] for row in gains], [Decimal(40), Decimal(20), Decimal(10)])
        self.assertTrue(all(isinstance(row["gain"], Decimal) for row in gains))

    def test_accounts_do_not_share_inventory(self):
        other = '''2022-01-01 * "Other account"
  Assets:Other 1 ABC {1 USD}
  Assets:Cash -1 USD
'''
        result = self.parse(OPEN + other + BUY + SELL)
        self.assertEqual(result[0]["cost_basis"], Decimal(10))
        self.assertEqual(result[0]["account"], "Assets:Brokerage")

    def test_total_price_currency_and_lot_selectors_are_rejected(self):
        alternatives = [SELL.replace(" @ 30 USD", " @@ 30 USD"),
                        SELL.replace(" @ 30 USD", " @ 30 EUR"),
                        SELL.replace("{10 USD}", '{10 USD, "lot"}'),
                        SELL.replace("{10 USD}", "{10 USD, 2023-01-01}"),
                        SELL.replace("{10 USD}", "{{10 USD}}")]
        for sale in alternatives:
            with self.subTest(sale=sale), self.assertRaises(ValueError):
                self.parse(OPEN + BUY + sale)
        with self.assertRaises(ValueError):
            self.parse(OPEN + BUY.replace("{10 USD}", "{10 EUR}") + SELL)

    def test_oversale_is_rejected_without_returning_partial_gains(self):
        with self.assertRaisesRegex(ValueError, "quantity"):
            self.parse(OPEN + BUY + SELL.replace("-1 ABC", "-2 ABC"))

    def test_explicit_cost_cannot_silently_bypass_fifo(self):
        second = '''2023-01-02 * "Second buy"
  Assets:Brokerage 1 ABC {20 USD}
  Assets:Cash -20 USD
'''
        with self.assertRaisesRegex(ValueError, "FIFO"):
            self.parse(OPEN + BUY + second + SELL.replace("{10 USD}", "{20 USD}"))

    def test_small_quantities_and_gains_are_not_rounded_away(self):
        ledger = OPEN + '''2023-01-01 * "Small buy"
  Assets:Brokerage 0.0000000001 ABC {10 USD}
  Assets:Cash -0.000000001 USD
2025-01-02 * "Small sale"
  Assets:Brokerage -0.0000000001 ABC {10 USD} @ 20 USD
  Assets:Cash 0.000000002 USD
  Income:Gains -0.000000001 USD
'''
        result = self.parse(ledger)
        self.assertEqual(result[0]["units"], Decimal("0.0000000001"))
        self.assertEqual(result[0]["gain"], Decimal("0.000000001"))

    def test_ambient_decimal_context_does_not_change_money(self):
        ledger = OPEN + BUY.replace("10 USD", "123.456 USD") + SELL.replace("{10 USD}", "{123.456 USD}").replace("30 USD", "234.567 USD").replace("-20 USD", "-111.111 USD")
        with localcontext() as context:
            context.prec = 2
            result = self.parse(ledger)
        self.assertEqual(result[0]["gain"], Decimal("111.111"))

    def test_unsupported_lines_dates_and_unbalanced_cash_are_rejected(self):
        ledgers = [OPEN + BUY + SELL.replace("Income:Gains -20 USD", "Income:Gains"),
                   OPEN + BUY + SELL.replace("Assets:Cash 30 USD", "Assets:Cash 29 USD"),
                   OPEN + BUY + SELL + 'option "title" "Ignored"\n',
                   OPEN + BUY + SELL + "  Expenses:Fees 1 USD\n",
                   OPEN + BUY + SELL.replace("2025-01-02", "2022-01-02"),
                   OPEN + BUY + SELL.replace("2025-01-02", "2025-02-30"),
                   OPEN + BUY + SELL.replace(" @ 30 USD", ""),
                   OPEN + BUY + SELL.replace("Assets:Brokerage", "Assets:Missing")]
        for ledger in ledgers:
            with self.subTest(ledger=ledger), self.assertRaises(ValueError):
                self.parse(ledger)

    def test_empty_or_directive_only_ledger_is_not_a_successful_trade_scan(self):
        for ledger in ("", "; only a comment\n", OPEN):
            with self.subTest(ledger=ledger), self.assertRaises(ValueError):
                self.parse(ledger)
        self.assertEqual(self.parse(OPEN + BUY), [])

    def test_calendar_classification_includes_losses_and_zero(self):
        oa = OAClient(token=None)
        skill = oa.get_skill(oa.start("example", "US")["skills_to_load"][0])
        gain = self.parse(OPEN + BUY + SELL)[0]
        for amount, outcome in ((Decimal(1), "gain"), (Decimal(-1), "loss"), (Decimal(0), "no gain or loss")):
            record = {**gain, "acquire_date": "2023-03-01", "sell_date": "2024-03-01", "holding_days": 366, "gain": amount}
            result = cap_gains_check.check(record, skill)
            self.assertEqual(result["term"], "short-term")
            self.assertIn(outcome, result["headline"].lower())
        result = cap_gains_check.check({**gain, "acquire_date": "2024-02-29"}, skill)
        self.assertFalse(result["complete"])
        changed = copy.deepcopy(skill)
        changed["rules"] = {"long_term_min_days": 366}
        self.assertFalse(cap_gains_check.check(gain, changed)["complete"])


if __name__ == "__main__":
    unittest.main()
