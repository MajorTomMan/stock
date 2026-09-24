from datetime import date
import time

from .database import Database
from .providers import BaoStockProvider, SzseProvider


class IngestionService:
    def __init__(self, db: Database, szse: SzseProvider):
        self.db = db
        self.szse = szse

    def _sync_master_dataset(self, dataset: str, fetch, persist) -> int:
        run_id = self.db.start_run("SZSE", dataset)
        try:
            result = fetch()
            self.db.add_raw_artifact(
                run_id,
                "SZSE",
                dataset,
                None,
                str(result.raw_path),
                result.sha256,
                result.byte_size,
            )
            count = persist(result.records)
            self.db.finish_run(run_id, count, {"raw_path": str(result.raw_path)})
            return count
        except Exception as exc:
            self.db.fail_run(run_id, exc)
            raise

    def sync_szse_master(self) -> dict[str, int]:
        return {
            "instrument": self._sync_master_dataset("instrument", self.szse.fetch_instruments, self.db.upsert_instruments),
            "delisted": self._sync_master_dataset("delisted", self.szse.fetch_delisted, self.db.upsert_instruments),
            "name_change": self._sync_master_dataset("name_change", self.szse.fetch_name_changes, self.db.upsert_name_changes),
        }

    def sync_szse_daily(self, trade_date: date) -> int:
        known = self.db.known_symbols("SZSE")
        if not known:
            raise RuntimeError("No SZSE instruments in database. Run sync-szse-master first.")

        run_id = self.db.start_run("SZSE", "stock_snapshot", trade_date, trade_date)
        try:
            result = self.szse.fetch_daily_snapshot(trade_date)
            artifact_id = self.db.add_raw_artifact(
                run_id,
                "SZSE",
                "stock_snapshot",
                trade_date,
                str(result.raw_path),
                result.sha256,
                result.byte_size,
            )
            bars = [bar for bar in result.records if bar.symbol in known]
            count = self.db.write_daily_bars(bars, artifact_id)
            self.db.finish_run(
                run_id,
                count,
                {
                    "raw_rows": len(result.records),
                    "accepted_a_share_rows": count,
                    "filtered_rows": len(result.records) - count,
                    "raw_path": str(result.raw_path),
                },
            )
            return count
        except Exception as exc:
            self.db.fail_run(run_id, exc)
            raise

    def bootstrap_baostock(
        self,
        start: date,
        end: date,
        codes: set[str] | None = None,
        limit: int | None = None,
        *,
        resume: bool = True,
        retries: int = 2,
        delay_seconds: float = 0.3,
    ) -> dict:
        """Run at most limit pending symbols; each completed symbol is a durable checkpoint.

        A checkpoint only matches the same requested effective date window.
        Changing --start/--end intentionally creates a new backfill window.
        """
        if start > end:
            raise ValueError("--start must not be after --end")
        if limit is not None and limit < 1:
            raise ValueError("--batch-size/--limit must be >= 1")
        if retries < 0 or retries > 10 or delay_seconds < 0:
            raise ValueError("--retries must be 0..10 and --delay must be >= 0")

        instruments = self.db.list_instruments("SZSE")
        if codes:
            instruments = [row for row in instruments if row[1] in codes]
            unknown = codes - {row[1] for row in instruments}
            if unknown:
                raise RuntimeError(f"Unknown instrument codes: {sorted(unknown)}")
        if not instruments:
            raise RuntimeError("No instruments selected. Run sync-szse-master first.")

        completed = self.db.completed_history_jobs() if resume else set()
        eligible = []
        skipped_existing = 0
        outside_window = 0
        for instrument_id, symbol, list_date, delist_date in instruments:
            actual_start = max(start, list_date) if list_date else start
            actual_end = min(end, delist_date) if delist_date else end
            if actual_start > actual_end:
                outside_window += 1
                continue
            if (symbol, actual_start, actual_end) in completed:
                skipped_existing += 1
                continue
            eligible.append((instrument_id, symbol, list_date, actual_start, actual_end))

        pending_total = len(eligible)
        selected = eligible[:limit] if limit is not None else eligible
        failures: list[dict] = []
        successful = 0
        total_rows = 0

        if not selected:
            return {
                "selected_instruments": len(instruments),
                "already_completed": skipped_existing,
                "outside_window": outside_window,
                "attempted": 0,
                "successful_instruments": 0,
                "failed_instruments": 0,
                "rows": 0,
                "remaining_pending": pending_total,
                "failures": [],
            }

        with BaoStockProvider() as provider:
            for number, (instrument_id, symbol, list_date, actual_start, actual_end) in enumerate(selected, 1):
                run_id = self.db.start_run(
                    provider.name, "daily_history", actual_start, actual_end,
                    {"symbol": symbol, "requested_start": start.isoformat(), "requested_end": end.isoformat()},
                )
                for attempt in range(1, retries + 2):
                    try:
                        bars = provider.fetch_daily(symbol, actual_start, actual_end)
                        count = self.db.write_daily_bars(bars)
                        if bars and list_date:
                            self.db.record_early_history_gap(
                                instrument_id, symbol, list_date, bars[0].trade_date, provider.name,
                            )
                        self.db.finish_run(
                            run_id, count,
                            {
                                "symbol": symbol,
                                "attempts": attempt,
                                "first_bar_date": bars[0].trade_date.isoformat() if bars else None,
                                "last_bar_date": bars[-1].trade_date.isoformat() if bars else None,
                                "empty_result": not bool(bars),
                                "requested_start": start.isoformat(),
                                "requested_end": end.isoformat(),
                            },
                        )
                        successful += 1
                        total_rows += count
                        print(f"[BAOSTOCK] [{number}/{len(selected)}] {symbol}: {count} rows (attempt {attempt})", flush=True)
                        break
                    except Exception as exc:
                        if attempt > retries:
                            self.db.fail_run(run_id, exc)
                            failures.append({"symbol": symbol, "error": str(exc)})
                            print(f"[BAOSTOCK] [{number}/{len(selected)}] {symbol}: FAILED: {exc}", flush=True)
                            break
                        print(f"[BAOSTOCK] {symbol}: retry {attempt}/{retries} after: {exc}", flush=True)
                        time.sleep(min(2 ** (attempt - 1), 30))
                        try:
                            provider.reconnect()
                        except Exception as reconnect_error:
                            print(f"[BAOSTOCK] {symbol}: reconnect failed: {reconnect_error}", flush=True)
                if delay_seconds:
                    time.sleep(delay_seconds)

        return {
            "selected_instruments": len(instruments),
            "already_completed": skipped_existing,
            "outside_window": outside_window,
            "attempted": len(selected),
            "successful_instruments": successful,
            "failed_instruments": len(failures),
            "rows": total_rows,
            "remaining_pending": pending_total - successful,
            "failures": failures,
        }
