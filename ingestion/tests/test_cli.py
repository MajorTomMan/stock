"""Offline regression tests for CLI dispatch and provider wiring."""

import io
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from stock_data import cli


class CliDispatchTests(TestCase):
    def test_ingestion_commands_dispatch_without_database_or_network(self):
        settings = SimpleNamespace(
            database_url="postgresql://unused",
            raw_data_dir=Path("/tmp/stock-data-test"),
            http_timeout_seconds=1,
        )
        cases = (
            (("sync-szse-master",), "sync_szse_master", (), {}),
            (("sync-sse-master",), "sync_sse_master", (), {}),
            (
                ("sync-szse-daily", "--date", "2025-09-01"),
                "sync_szse_daily",
                (date(2025, 9, 1),),
                {},
            ),
            (("sync-sse-daily",), "sync_sse_daily", (), {}),
            (
                (
                    "sync-szse-range",
                    "--start",
                    "2025-09-01",
                    "--end",
                    "2025-09-05",
                    "--batch-size",
                    "2",
                    "--delay",
                    "0",
                    "--force",
                    "--retry-empty",
                ),
                "sync_szse_range",
                (date(2025, 9, 1), date(2025, 9, 5)),
                {
                    "batch_size": 2,
                    "delay_seconds": 0.0,
                    "force": True,
                    "retry_empty": True,
                },
            ),
            (
                (
                    "bootstrap-baostock",
                    "--exchange",
                    "SSE",
                    "--start",
                    "1990-12-19",
                    "--end",
                    "2025-08-31",
                    "--codes",
                    "600000.SH",
                    "--batch-size",
                    "1",
                    "--delay",
                    "0",
                    "--retries",
                    "1",
                ),
                "bootstrap_baostock",
                (date(1990, 12, 19), date(2025, 8, 31), {"600000"}, 1),
                {
                    "exchange": "SSE",
                    "resume": True,
                    "retries": 1,
                    "delay_seconds": 0.0,
                },
            ),
        )

        with patch.object(cli.Settings, "from_env", return_value=settings), \
             patch.object(cli, "Database") as database_cls, \
             patch.object(cli, "SzseProvider") as szse_cls, \
             patch.object(cli, "SseProvider") as sse_cls, \
             patch.object(cli, "IngestionService") as service_cls:
            service = service_cls.return_value
            service.sync_szse_master.return_value = {}
            service.sync_sse_master.return_value = {}
            service.sync_szse_daily.return_value = 0
            service.sync_sse_daily.return_value = {}
            service.sync_szse_range.return_value = {"failed_dates": []}
            service.bootstrap_baostock.return_value = {}

            for argv, method_name, expected_args, expected_kwargs in cases:
                with self.subTest(command=argv[0]):
                    with patch.object(sys, "argv", ["stock_data.cli", *argv]), \
                         patch("sys.stdout", new_callable=io.StringIO):
                        cli.main()

                    database_cls.assert_called_once_with(settings.database_url)
                    szse_cls.assert_called_once_with(
                        settings.raw_data_dir,
                        settings.http_timeout_seconds,
                    )
                    sse_cls.assert_called_once_with(
                        settings.raw_data_dir,
                        settings.http_timeout_seconds,
                    )
                    service_cls.assert_called_once_with(
                        database_cls.return_value,
                        szse_cls.return_value,
                        sse_cls.return_value,
                    )
                    getattr(service, method_name).assert_called_once_with(
                        *expected_args,
                        **expected_kwargs,
                    )

                    database_cls.reset_mock()
                    szse_cls.reset_mock()
                    sse_cls.reset_mock()
                    service_cls.reset_mock()

    def test_help_does_not_construct_database(self):
        with patch.object(cli, "Database") as database_cls, \
             patch.object(sys, "argv", ["stock_data.cli", "--help"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 0)
        database_cls.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
