"""Offline tests for official daily publication quality gates."""
from datetime import date
from unittest import TestCase

from stock_data.quality import audit_snapshot


DAY = date(2025, 9, 1)


def sample(**overrides):
    row = {
        "instrument_id": 1, "symbol": "000001", "open": 11,
        "high": 12, "low": 10, "close": 11.5,
        "volume_shares": 1234, "turnover_cny": 18000,
        "selected_source": "SZSE", "baostock_close": 11.5,
    }
    row.update(overrides)
    return row


class DailySnapshotQualityTests(TestCase):
    def test_valid_snapshot_with_agreeing_sources(self):
        result = audit_snapshot(DAY, [sample()], 1_000, 1, min_coverage=0.001)
        self.assertEqual(result["status"], "STAGED")

    def test_suspension_nullable_ohlc_is_not_fabricated(self):
        result = audit_snapshot(
            DAY, [sample(open=None, high=None, low=None, close=None,
                         volume_shares=None, turnover_cny=None,
                         baostock_close=None)], 30, 1, min_coverage=0.01,
        )
        self.assertEqual(result["blocker_count"], 0)

    def test_absent_and_incomplete_snapshot_are_blocked(self):
        result = audit_snapshot(DAY, [], 2000, 0)
        self.assertIn("SNAPSHOT_EMPTY", {i.issue_type for i in result["blockers"]})
        result = audit_snapshot(DAY, [sample()], 2000, 1)
        self.assertIn("SNAPSHOT_LOW_COVERAGE", {i.issue_type for i in result["blockers"]})

    def test_source_count_disagrees_with_import(self):
        result = audit_snapshot(DAY, [sample()], 30, 20, min_coverage=0.01)
        self.assertIn("SNAPSHOT_SOURCE_COUNT", {i.issue_type for i in result["blockers"]})

    def test_invalid_ohlc_blocks_publication(self):
        result = audit_snapshot(DAY, [sample(high=10, volume_shares=-1)], 30, 1,
                                min_coverage=0.01)
        self.assertIn("OHLC_INVALID", {i.issue_type for i in result["blockers"]})

    def test_source_difference_is_warning_not_automatic_replacement(self):
        result = audit_snapshot(DAY, [sample(baostock_close=11.6)], 30, 1,
                                min_coverage=0.01)
        self.assertEqual(result["blocker_count"], 0)
        self.assertEqual(result["warnings"][0].issue_type, "SOURCE_CLOSE_MISMATCH")

    def test_small_unknown_master_baseline_does_not_auto_publish(self):
        result = audit_snapshot(DAY, [sample()], 1, 1)
        self.assertIn("SNAPSHOT_BASELINE_UNAVAILABLE",
                      {i.issue_type for i in result["blockers"]})
