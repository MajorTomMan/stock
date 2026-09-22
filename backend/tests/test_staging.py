"""No-network tests for the SZSE staging boundary."""
from datetime import date
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from stock_data.ingestion import IngestionService


DAY = date(2025, 9, 1)


class StubDatabase:
    def __init__(self, events):
        self.events = events

    def known_symbols(self, exchange):
        return {"000001"}

    def start_run(self, *args):
        self.events.append("start_run")
        return 123

    def add_raw_artifact(self, *args):
        self.events.append("add_raw")
        return 4

    def write_daily_bars(self, bars, artifact_id=None):
        self.events.append("write_bars")
        return len(bars)

    def finish_run(self, *args):
        self.events.append("finish_run")

    def fail_run(self, *args):
        self.events.append("fail_run")


class StubPublication:
    def __init__(self, events):
        self.events = events

    def stage(self, trade_date, run_id):
        self.events.append("stage")

    def fail_import(self, *args):
        self.events.append("block")


class StubSzse:
    def __init__(self, actual_day):
        self.actual_day = actual_day

    def fetch_daily_snapshot(self, trade_date):
        return SimpleNamespace(
            records=[SimpleNamespace(symbol="000001", trade_date=self.actual_day)],
            raw_path="/tmp/fake.xlsx", sha256="a" * 64, byte_size=12,
        )


class StagingTests(TestCase):
    def test_ingest_stages_before_mutation_and_does_not_publish(self):
        events = []
        with patch("stock_data.ingestion.PublicationService",
                   return_value=StubPublication(events)):
            count = IngestionService(StubDatabase(events), StubSzse(DAY)).sync_szse_daily(DAY)
        self.assertEqual(count, 1)
        self.assertEqual(events, [
            "start_run", "stage", "add_raw", "write_bars", "finish_run",
        ])

    def test_wrong_snapshot_date_blocks_and_does_not_write(self):
        events = []
        with patch("stock_data.ingestion.PublicationService",
                   return_value=StubPublication(events)):
            with self.assertRaisesRegex(ValueError, "outside the requested"):
                IngestionService(
                    StubDatabase(events), StubSzse(date(2025, 9, 2)),
                ).sync_szse_daily(DAY)
        self.assertEqual(events, ["start_run", "stage", "fail_run", "block"])
