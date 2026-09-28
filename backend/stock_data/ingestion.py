from datetime import date
import time

from .database import Database
from .providers import BaoStockProvider, SseProvider, SzseProvider


class IngestionService:
    def __init__(self, db: Database, szse: SzseProvider | None = None, sse: SseProvider | None = None):
        self.db = db
        self.szse = szse
        self.sse = sse

    def _sync_master_dataset(self, provider: str, dataset: str, fetch, persist) -> int:
        run_id = self.db.start_run(provider, dataset)
        try:
            result = fetch()
            self.db.add_raw_artifact(
                run_id,
                provider,
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
        if self.szse is None:
            raise RuntimeError("SZSE provider is not configured")
        return {
            "instrument": self._sync_master_dataset("SZSE", "instrument", self.szse.fetch_instruments, self.db.upsert_instruments),
            "delisted": self._sync_master_dataset("SZSE", "delisted", self.szse.fetch_delisted, self.db.upsert_instruments),
            "name_change": self._sync_master_dataset("SZSE", "name_change", self.szse.fetch_name_changes, self.db.upsert_name_changes),
        }

    def sync_sse_master(self) -> dict[str, int]:
        if self.sse is None:
            raise RuntimeError("SSE provider is not configured")
        return {
            "instrument": self._sync_master_dataset("SSE", "instrument", self.sse.fetch_instruments, self.db.upsert_instruments),
            "delisted": self._sync_master_dataset("SSE", "delisted", self.sse.fetch_delisted, self.db.upsert_instruments),
        }

    def sync_szse_daily(self, trade_date: date) -> int:
        if self.szse is None:
            raise RuntimeError("SZSE provider is not configured")
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

    def sync_sse_daily(self) -> dict:
        if self.sse is None:
            raise RuntimeError("SSE provider is not configured")
        known = self.db.known_symbols("SSE")
        if not known:
            raise RuntimeError("No SSE instruments in database. Run sync-sse-master first.")

        result = self.sse.fetch_daily_snapshot()
        trade_date = result.business_date
        if trade_date is None:
            raise RuntimeError("SSE snapshot did not provide a market date")

        run_id = self.db.start_run("SSE", "stock_snapshot", trade_date, trade_date)
        try:
            artifact_id = self.db.add_raw_artifact(
                run_id,
                "SSE",
                "stock_snapshot",
                trade_date,
                str(result.raw_path),
                result.sha256,
                result.byte_size,
            )
            bars = [bar for bar in result.records if bar.symbol in known and bar.trade_date == trade_date]
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
            return {"date": trade_date.isoformat(), "rows": count, "raw_rows": len(result.records)}
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
        exchange: str = "SZSE",
        resume: bool = True,
        retries: int = 2,
        delay_seconds: float = 0.3,
    ) -> dict:
        """Run at most limit pending symbols; each completed symbol is a durable checkpoint.

        A checkpoint only matches the same exchange, symbol and effective date window.
        Legacy checkpoints without exchange metadata are treated as SZSE jobs.
        """
        exchange = exchange.upper()
        if exchange not in {"SZSE", "SSE"}:
            raise ValueError("--exchange must be SZSE or SSE")
        if start > end:
            raise ValueError("--start must not be after --end")
        if limit is not None and limit < 1:
            raise ValueError("--batch-size/--limit must be >= 1")
        if retries < 0 or retries > 10 or delay_seconds < 0:
            raise ValueError("--retries must be 0..10 and --delay must be >= 0")

        instruments = self.db.list_instruments(exchange)
        if codes:
            instruments = [row for row in instruments if row[1] in codes]
            unknown = codes - {row[1] for row in instruments}
            if unknown:
                raise RuntimeError(f"Unknown {exchange} instrument codes: {sorted(unknown)}")
        if not instruments:
            command = "sync-szse-master" if exchange == "SZSE" else "sync-sse-master"
            raise RuntimeError(f"No {exchange} instruments selected. Run {command} first.")

        completed = self.db.completed_history_jobs(exchange) if resume else set()
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
                "exchange": exchange,
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

        with BaoStockProvider(exchange=exchange) as provider:
            for number, (instrument_id, symbol, list_date, actual_start, actual_end) in enumerate(selected, 1):
                run_id = self.db.start_run(
                    provider.name,
                    "daily_history",
                    actual_start,
                    actual_end,
                    {
                        "exchange": exchange,
                        "symbol": symbol,
                        "requested_start": start.isoformat(),
                        "requested_end": end.isoformat(),
                    },
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
                            run_id,
                            count,
                            {
                                "exchange": exchange,
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
                        print(
                            f"[BAOSTOCK:{exchange}] [{number}/{len(selected)}] {symbol}: "
                            f"{count} rows (attempt {attempt})",
                            flush=True,
                        )
                        break
                    except Exception as exc:
                        if attempt > retries:
                            self.db.fail_run(run_id, exc)
                            failures.append({"symbol": symbol, "error": str(exc)})
                            print(
                                f"[BAOSTOCK:{exchange}] [{number}/{len(selected)}] {symbol}: FAILED: {exc}",
                                flush=True,
                            )
                            break
                        print(
                            f"[BAOSTOCK:{exchange}] {symbol}: retry {attempt}/{retries} after: {exc}",
                            flush=True,
                        )
                        time.sleep(min(2 ** (attempt - 1), 30))
                        try:
                            provider.reconnect()
                        except Exception as reconnect_error:
                            print(
                                f"[BAOSTOCK:{exchange}] {symbol}: reconnect failed: {reconnect_error}",
                                flush=True,
                            )
                if delay_seconds:
                    time.sleep(delay_seconds)

        return {
            "exchange": exchange,
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
