"""Unit tests for resumable imports; does not need a live database or network."""
from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from stock_data.ingestion import IngestionService


START = date(1991, 1, 1)
END = date(2025, 8, 31)


class FakeDB:
    def __init__(self, done=()):
        self.done = set(done)
        self.starts = []
        self.finishes = []
        self.fails = []

    def list_instruments(self, exchange):
        return [
            (1, "000001", date(1991, 4, 3), None),
            (2, "000004", date(1990, 12, 1), date(2026, 7, 14)),
            (3, "300001", date(2009, 10, 30), None),
        ]

    def completed_history_jobs(self):
        return self.done

    def start_run(self, provider, dataset, start, end, metadata=None):
        self.starts.append((metadata["symbol"], start, end))
        return len(self.starts)

    def write_daily_bars(self, bars):
        return len(bars)

    def record_early_history_gap(self, *args):
        pass

    def finish_run(self, run_id, count, metadata=None):
        self.finishes.append((run_id, count, metadata))

    def fail_run(self, run_id, exc):
        self.fails.append((run_id, str(exc)))


class FakeProvider:
    name = "BAOSTOCK"
    seen = []
    fail_once = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def reconnect(self):
        pass

    def fetch_daily(self, symbol, start, end):
        self.seen.append(symbol)
        if self.fail_once and symbol == "000004":
            self.fail_once = False
            raise OSError("temporary socket failure")
        return [SimpleNamespace(trade_date=start)]


class BootstrapTests(TestCase):
    def setUp(self):
        FakeProvider.seen = []
        FakeProvider.fail_once = False

    def test_resume_skips_exact_completed_window(self):
        db = FakeDB({("000001", date(1991, 4, 3), END)})
        with patch("stock_data.ingestion.BaoStockProvider", FakeProvider):
            result = IngestionService(db, None).bootstrap_baostock(
                START, END, limit=1, delay_seconds=0,
            )
        self.assertEqual(result["already_completed"], 1)
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(FakeProvider.seen, ["000004"])
        self.assertEqual(db.starts[0][0], "000004")

    def test_failed_symbol_retries_without_discarding_others(self):
        FakeProvider.fail_once = True
        db = FakeDB()
        with patch("stock_data.ingestion.BaoStockProvider", FakeProvider), patch("stock_data.ingestion.time.sleep"):
            result = IngestionService(db, None).bootstrap_baostock(
                START, END, retries=1, delay_seconds=0,
            )
        self.assertEqual(result["successful_instruments"], 3)
        self.assertEqual(result["failed_instruments"], 0)
        self.assertEqual(FakeProvider.seen.count("000004"), 2)

    def test_outside_listing_window_is_not_queried(self):
        db = FakeDB()
        with patch("stock_data.ingestion.BaoStockProvider", FakeProvider):
            result = IngestionService(db, None).bootstrap_baostock(
                date(2000, 1, 1), date(2000, 1, 31), delay_seconds=0,
            )
        self.assertEqual(result["outside_window"], 1)
        self.assertNotIn("300001", FakeProvider.seen)


class LoginRetryTests(TestCase):
    def test_initial_login_recovers_from_network_receive_error(self):
        from stock_data.providers.baostock_provider import BaoStockProvider
        failures = [
            SimpleNamespace(error_code="10002007", error_msg="network receive error"),
            SimpleNamespace(error_code="0", error_msg="success"),
        ]
        with patch("stock_data.providers.baostock_provider.bs.login", side_effect=failures) as login, \
             patch("stock_data.providers.baostock_provider.bs.logout") as logout, \
             patch("stock_data.providers.baostock_provider.time.sleep") as sleep:
            with BaoStockProvider():
                pass
        self.assertEqual(login.call_count, 2)
        sleep.assert_called_once_with(2)
        self.assertEqual(logout.call_count, 2)  # cleanup before retry + context exit

    def test_initial_login_final_failure_is_bounded(self):
        from stock_data.providers.baostock_provider import BaoStockProvider
        failure = SimpleNamespace(error_code="10002007", error_msg="network receive error")
        with patch("stock_data.providers.baostock_provider.bs.login", return_value=failure) as login, \
             patch("stock_data.providers.baostock_provider.bs.logout"), \
             patch("stock_data.providers.baostock_provider.time.sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "failed after 4 attempts"):
                with BaoStockProvider():
                    pass
        self.assertEqual(login.call_count, 4)
        self.assertEqual(sleep.call_count, 3)

    def test_reconnect_uses_same_login_retry(self):
        from stock_data.providers.baostock_provider import BaoStockProvider
        failures = [
            OSError("Broken pipe"),
            SimpleNamespace(error_code="0", error_msg="success"),
        ]
        with patch("stock_data.providers.baostock_provider.bs.login", side_effect=failures) as login, \
             patch("stock_data.providers.baostock_provider.bs.logout"), \
             patch("stock_data.providers.baostock_provider.time.sleep"):
            BaoStockProvider().reconnect()
        self.assertEqual(login.call_count, 2)
