from datetime import date

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

    def bootstrap_baostock(self, start: date, end: date, codes: set[str] | None = None, limit: int | None = None) -> dict:
        instruments = self.db.list_instruments("SZSE")
        if codes:
            instruments = [row for row in instruments if row[1] in codes]
        if limit is not None:
            instruments = instruments[:limit]
        if not instruments:
            raise RuntimeError("No instruments selected. Run sync-szse-master first or check --codes.")

        total_rows = 0
        success = 0
        failures: list[dict] = []
        with BaoStockProvider() as provider:
            for instrument_id, symbol, list_date, delist_date in instruments:
                actual_start = max(start, list_date) if list_date else start
                actual_end = min(end, delist_date) if delist_date else end
                if actual_start > actual_end:
                    continue
                run_id = self.db.start_run(provider.name, "daily_history", actual_start, actual_end)
                try:
                    bars = provider.fetch_daily(symbol, actual_start, actual_end)
                    count = self.db.write_daily_bars(bars)
                    total_rows += count
                    success += 1
                    if bars and list_date:
                        self.db.record_early_history_gap(
                            instrument_id,
                            symbol,
                            list_date,
                            bars[0].trade_date,
                            provider.name,
                        )
                    self.db.finish_run(
                        run_id,
                        count,
                        {
                            "symbol": symbol,
                            "first_bar_date": bars[0].trade_date.isoformat() if bars else None,
                            "last_bar_date": bars[-1].trade_date.isoformat() if bars else None,
                        },
                    )
                    print(f"[BAOSTOCK] {symbol}: {count} rows")
                except Exception as exc:
                    self.db.fail_run(run_id, exc)
                    failures.append({"symbol": symbol, "error": str(exc)})
                    print(f"[BAOSTOCK] {symbol}: FAILED: {exc}")

        return {
            "selected_instruments": len(instruments),
            "successful_instruments": success,
            "failed_instruments": len(failures),
            "rows": total_rows,
            "failures": failures,
        }
