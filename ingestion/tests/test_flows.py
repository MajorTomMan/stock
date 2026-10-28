"""Offline checks for Prefect wrappers; no real server, PostgreSQL, or network."""
import io
import sys
from datetime import date
from unittest import TestCase
from unittest.mock import patch, Mock

from stock_data import flows, workflow_cli


class PrefectTaskTests(TestCase):
    def test_master_routes_exchange_to_existing_service(self):
        with patch.object(flows, "_service") as factory, \
             patch.object(flows, "get_run_logger") as logger:
            service = factory.return_value
            service.sync_szse_master.return_value = {"instrument": 10}
            self.assertEqual(flows.master_task.fn("SZSE"), {"instrument": 10})
            service.sync_szse_master.assert_called_once_with()
            service.sync_sse_master.assert_not_called()
            logger.assert_called()

    def test_sse_daily_uses_provider_reported_date(self):
        with patch.object(flows, "_service") as factory, \
             patch.object(flows, "get_run_logger"):
            service = factory.return_value
            service.sync_sse_daily.return_value = {"date": "2026-10-27", "rows": 100}
            result = flows.daily_task.fn("SSE", date(2026, 10, 28))
            self.assertEqual(result["date"], "2026-10-27")
            service.sync_sse_daily.assert_called_once_with()

    def test_szse_daily_requires_explicit_date(self):
        with patch.object(flows, "_service"), \
             patch.object(flows, "get_run_logger"):
            with self.assertRaisesRegex(ValueError, "explicit snapshot date"):
                flows.daily_task.fn("SZSE")

    def test_partial_history_failure_is_not_reported_success(self):
        with patch.object(flows, "_service") as factory, \
             patch.object(flows, "get_run_logger"):
            factory.return_value.bootstrap_baostock.return_value = {
                "failed_instruments": 1,
                "failures": [{"symbol": "600000", "error": "connection reset"}],
            }
            with self.assertRaisesRegex(RuntimeError, "600000"):
                flows.history_task.fn(
                    date(1990, 12, 19), date(2025, 8, 31), "SSE",
                    ["600000"], 1, 0, 0, False,
                )
            factory.return_value.bootstrap_baostock.assert_called_once_with(
                date(1990, 12, 19), date(2025, 8, 31),
                {"600000"}, 1, exchange="SSE", resume=True,
                retries=0, delay_seconds=0,
            )

    def test_partial_range_failure_is_not_reported_success(self):
        with patch.object(flows, "_service") as factory, \
             patch.object(flows, "get_run_logger"):
            factory.return_value.sync_szse_range.return_value = {
                "failed_dates": [{"date": "2026-10-28", "error": "timeout"}]
            }
            with self.assertRaisesRegex(RuntimeError, "2026-10-28"):
                flows.szse_range_task.fn(date(2026, 10, 27), date(2026, 10, 28))

    def test_daily_flow_continues_other_exchange_after_failure(self):
        with patch.object(flows, "master_task") as master, \
             patch.object(flows, "daily_task") as daily, \
             patch.object(flows, "get_run_logger"):
            def run_daily(exchange, trade_date):
                if exchange == "SZSE":
                    raise RuntimeError("SZSE failed")
                return {"rows": 12, "date": "2026-10-27"}
            daily.side_effect = run_daily
            with self.assertRaisesRegex(RuntimeError, "SZSE"):
                flows.market_daily_flow.fn(date(2026, 10, 28))
            self.assertEqual([call.args[0] for call in daily.call_args_list],
                             ["SZSE", "SSE"])
            self.assertEqual(master.call_count, 2)

    def test_invalid_exchange_is_rejected(self):
        with self.assertRaises(ValueError):
            flows.market_master_flow.fn("BSE")


class WorkflowCliTests(TestCase):
    def test_history_defaults_to_sse_start_and_normalizes_codes(self):
        with patch.object(workflow_cli, "market_history_flow") as history, \
             patch.object(sys, "argv", ["workflows", "history", "--exchange", "SSE",
                                         "--end", "2025-08-31", "--codes", "600000.SH"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            history.return_value = {"attempted": 1}
            workflow_cli.main()
        self.assertEqual(history.call_args.args[:4],
                         (date(1990, 12, 19), date(2025, 8, 31), "SSE", ["600000"]))

    def test_help_has_no_database_side_effects(self):
        with patch.object(sys, "argv", ["workflows", "--help"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as result:
                workflow_cli.main()
        self.assertEqual(result.exception.code, 0)
