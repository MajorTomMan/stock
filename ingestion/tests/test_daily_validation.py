"""Offline tests for the validation boundary."""

import unittest
from datetime import date
from decimal import Decimal

from ingestion.src.source.bao.model.daily_bar import BaoDailyBar
from ingestion.src.task.daily_validation import validate_daily_bars
from ingestion.src.task.task_result import TaskResult
from ingestion.src.task.stock_task import StockTask


class DailyValidationTests(unittest.TestCase):
    def bar(self, **changes):
        fields = dict(
            date=date(2023, 1, 3), code="sh.600000",
            open=Decimal("10"), high=Decimal("12"),
            low=Decimal("9"), close=Decimal("11"),
            pre_close=Decimal("10"), volume=100, amount=Decimal("1100")
        )
        fields.update(changes)
        return BaoDailyBar(**fields)

    def test_valid_bar_passes_unchanged(self):
        bar = self.bar()
        result = validate_daily_bars([bar])
        self.assertEqual(result.valid, [bar])
        self.assertEqual(result.invalid, [])

    def test_bad_bar_keeps_original_and_reasons(self):
        bad = self.bar(close=Decimal("13"), amount=Decimal("-1"))
        result = validate_daily_bars([self.bar(), bad])
        self.assertEqual(len(result.valid), 1)
        self.assertEqual(result.invalid[0].bar, bad)
        self.assertIn("close outside low/high range", result.invalid[0].reasons)
        self.assertIn("amount must be non-negative", result.invalid[0].reasons)

    def test_missing_prices_and_zero_volume_are_not_rejected(self):
        bar = self.bar(open=None, high=None, low=None, close=None,
                       volume=0, amount=Decimal("0"))
        self.assertEqual(validate_daily_bars([bar]).valid, [bar])

    def test_duplicates_are_not_implicitly_removed(self):
        bar = self.bar()
        self.assertEqual(len(validate_daily_bars([bar, bar]).valid), 2)

    def test_negative_price_rejected(self):
        result = validate_daily_bars([self.bar(open=Decimal("-1"))])
        self.assertIn("open must be positive", result.invalid[0].reasons)

    def test_task_result_imports_stock_task(self):
        task = StockTask(task_id="1", source="bao", dataset="daily")
        self.assertEqual(TaskResult(task, "fetch", []).task, task)


if __name__ == "__main__":
    unittest.main()
