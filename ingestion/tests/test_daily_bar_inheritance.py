"""Offline checks for model inheritance and BaoStock field mapping."""

import unittest
from dataclasses import fields
from datetime import date
from decimal import Decimal

from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


class DailyBarInheritanceTests(unittest.TestCase):
    def test_bao_bar_inherits_common_fields(self):
        bar = BaoDailyBar(
            trade_date=date(2023, 1, 3), symbol="sh.600000",
            open=Decimal("10.20"), volume=100,
            turnover_rate=Decimal("1.2"),
        )
        self.assertIsInstance(bar, DailyBar)
        self.assertEqual(bar.symbol, "sh.600000")
        self.assertEqual(bar.open, Decimal("10.20"))
        self.assertEqual(bar.turnover_rate, Decimal("1.2"))

    def test_field_mapping_uses_provider_names_and_has_no_classvar(self):
        names = BaoDailyBar.to_fields().split(",")
        self.assertEqual(names[:2], ["date", "code"])
        self.assertIn("preclose", names)
        self.assertIn("pctChg", names)
        self.assertIn("isST", names)
        self.assertIn("pcfNcfTTM", names)
        self.assertNotIn("trade_date", names)
        self.assertNotIn("symbol", names)
        self.assertNotIn("source_fields", [f.name for f in fields(BaoDailyBar)])
        self.assertEqual(len(names), len(set(names)))

    def test_base_model_does_not_carry_provider_fields(self):
        names = {f.name for f in fields(DailyBar)}
        self.assertEqual(names, {
            "trade_date", "symbol", "open", "high", "low", "close",
            "pre_close", "volume", "amount", "pct_change",
        })
        self.assertNotIn("adjust_flag", names)
        self.assertNotIn("pe_ttm", names)


if __name__ == "__main__":
    unittest.main()
