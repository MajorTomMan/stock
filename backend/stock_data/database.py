import json
from contextlib import contextmanager
from datetime import date
from typing import Iterable

import psycopg

from .migrations import MIGRATIONS
from .models import DailyBar, InstrumentRecord, NameChangeRecord


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextmanager
    def connect(self):
        with psycopg.connect(self.dsn) as conn:
            yield conn

    def migrate(self) -> None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migration (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            cur.execute("SELECT version FROM schema_migration")
            applied = {row[0] for row in cur.fetchall()}
            for version, name, sql in MIGRATIONS:
                if version in applied:
                    continue
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migration(version, name) VALUES (%s, %s)", (version, name))

    def start_run(self, provider: str, dataset: str, start: date | None = None, end: date | None = None, metadata: dict | None = None) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingestion_run(provider, dataset, requested_from, requested_to, metadata) VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING id",
                (provider, dataset, start, end, json.dumps(metadata or {})),
            )
            return cur.fetchone()[0]

    def finish_run(self, run_id: int, row_count: int, metadata: dict | None = None) -> None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE ingestion_run SET status='SUCCESS', row_count=%s, metadata=%s::jsonb, finished_at=now() WHERE id=%s",
                (row_count, json.dumps(metadata or {}), run_id),
            )

    def fail_run(self, run_id: int, error: Exception) -> None:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE ingestion_run SET status='FAILED', error_message=%s, finished_at=now() WHERE id=%s",
                (str(error), run_id),
            )

    def add_raw_artifact(self, run_id: int, provider: str, dataset: str, business_date: date | None, path: str, sha256: str, byte_size: int) -> int:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw_artifact(ingestion_run_id,provider,dataset,business_date,file_path,sha256,byte_size)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(provider,dataset,sha256) DO UPDATE SET file_path=EXCLUDED.file_path
                RETURNING id
                """,
                (run_id, provider, dataset, business_date, path, sha256, byte_size),
            )
            return cur.fetchone()[0]

    def upsert_instruments(self, records: Iterable[InstrumentRecord]) -> int:
        rows = list(records)
        if not rows:
            return 0
        sql = """
            INSERT INTO instrument(
                exchange,symbol,current_name,full_name,english_name,security_type,board,list_date,delist_date,status,
                registered_address,region,province,city,industry,website,source
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(exchange,symbol) DO UPDATE SET
                current_name=COALESCE(EXCLUDED.current_name,instrument.current_name),
                full_name=COALESCE(EXCLUDED.full_name,instrument.full_name),
                english_name=COALESCE(EXCLUDED.english_name,instrument.english_name),
                security_type=COALESCE(EXCLUDED.security_type,instrument.security_type),
                board=COALESCE(EXCLUDED.board,instrument.board),
                list_date=COALESCE(EXCLUDED.list_date,instrument.list_date),
                delist_date=COALESCE(EXCLUDED.delist_date,instrument.delist_date),
                status=CASE WHEN EXCLUDED.status='UNKNOWN' THEN instrument.status ELSE EXCLUDED.status END,
                registered_address=COALESCE(EXCLUDED.registered_address,instrument.registered_address),
                region=COALESCE(EXCLUDED.region,instrument.region),province=COALESCE(EXCLUDED.province,instrument.province),
                city=COALESCE(EXCLUDED.city,instrument.city),industry=COALESCE(EXCLUDED.industry,instrument.industry),
                website=COALESCE(EXCLUDED.website,instrument.website),source=EXCLUDED.source,updated_at=now()
        """
        params = [(
            r.exchange,r.symbol,r.current_name,r.full_name,r.english_name,r.security_type,r.board,r.list_date,
            r.delist_date,r.status,r.registered_address,r.region,r.province,r.city,r.industry,r.website,r.source,
        ) for r in rows]
        with self.connect() as conn, conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(rows)

    def upsert_name_changes(self, records: Iterable[NameChangeRecord]) -> int:
        rows = list(records)
        if not rows:
            return 0
        with self.connect() as conn, conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO instrument(exchange,symbol,current_name,source) VALUES (%s,%s,%s,%s) ON CONFLICT(exchange,symbol) DO NOTHING",
                    (r.exchange, r.symbol, r.after_name or r.before_name, r.source),
                )
                cur.execute(
                    """
                    INSERT INTO instrument_name_history(instrument_id,effective_date,before_name,after_name,source)
                    SELECT id,%s,%s,%s,%s FROM instrument WHERE exchange=%s AND symbol=%s
                    ON CONFLICT(instrument_id,effective_date,before_name,after_name,source) DO NOTHING
                    """,
                    (r.effective_date,r.before_name,r.after_name,r.source,r.exchange,r.symbol),
                )
        return len(rows)

    def list_instruments(self, exchange: str = "SZSE") -> list[tuple[int, str, date | None, date | None]]:
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT id,symbol,list_date,delist_date FROM instrument WHERE exchange=%s ORDER BY symbol", (exchange,))
            return cur.fetchall()

    def known_symbols(self, exchange: str = "SZSE") -> set[str]:
        return {row[1] for row in self.list_instruments(exchange)}

    def completed_history_jobs(self) -> set[tuple[str, date, date]]:
        """Successful per-symbol windows: only an exact match is safe to skip."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT metadata->>'symbol', requested_from, requested_to
                FROM ingestion_run
                WHERE provider='BAOSTOCK' AND dataset='daily_history'
                  AND status='SUCCESS' AND metadata ? 'symbol'
                  AND requested_from IS NOT NULL AND requested_to IS NOT NULL
                """
            )
            return {(symbol, start, end) for symbol, start, end in cur.fetchall() if symbol}

    def write_daily_bars(self, bars: Iterable[DailyBar], raw_artifact_id: int | None = None) -> int:
        rows = list(bars)
        if not rows:
            return 0
        exchanges: dict[str, set[str]] = {}
        for bar in rows:
            exchanges.setdefault(bar.exchange, set()).add(bar.symbol)

        observation_sql = """
            INSERT INTO market_daily_observation(
                instrument_id,trade_date,source,source_priority,pre_close,open,high,low,close,volume_shares,
                turnover_cny,pct_change,pe_ratio,trade_status,is_st,raw_artifact_id,extra
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(instrument_id,trade_date,source) DO UPDATE SET
                source_priority=EXCLUDED.source_priority,pre_close=EXCLUDED.pre_close,open=EXCLUDED.open,
                high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume_shares=EXCLUDED.volume_shares,
                turnover_cny=EXCLUDED.turnover_cny,pct_change=EXCLUDED.pct_change,pe_ratio=EXCLUDED.pe_ratio,
                trade_status=EXCLUDED.trade_status,is_st=EXCLUDED.is_st,raw_artifact_id=EXCLUDED.raw_artifact_id,
                extra=EXCLUDED.extra,ingested_at=now()
        """
        canonical_sql = """
            INSERT INTO market_daily(
                instrument_id,trade_date,pre_close,open,high,low,close,volume_shares,turnover_cny,pct_change,
                pe_ratio,trade_status,is_st,selected_source,source_priority
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(instrument_id,trade_date) DO UPDATE SET
                pre_close=EXCLUDED.pre_close,open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
                close=EXCLUDED.close,volume_shares=EXCLUDED.volume_shares,turnover_cny=EXCLUDED.turnover_cny,
                pct_change=EXCLUDED.pct_change,pe_ratio=EXCLUDED.pe_ratio,trade_status=EXCLUDED.trade_status,
                is_st=EXCLUDED.is_st,selected_source=EXCLUDED.selected_source,source_priority=EXCLUDED.source_priority,
                updated_at=now()
            WHERE EXCLUDED.source_priority <= market_daily.source_priority
        """

        with self.connect() as conn, conn.cursor() as cur:
            ids: dict[tuple[str, str], int] = {}
            for exchange, symbols in exchanges.items():
                symbol_list = sorted(symbols)
                cur.execute("SELECT id,symbol FROM instrument WHERE exchange=%s AND symbol=ANY(%s)", (exchange, symbol_list))
                for instrument_id, symbol in cur.fetchall():
                    ids[(exchange, symbol)] = instrument_id
                missing = [symbol for symbol in symbol_list if (exchange, symbol) not in ids]
                if missing:
                    cur.executemany(
                        "INSERT INTO instrument(exchange,symbol,source) VALUES (%s,%s,%s) ON CONFLICT(exchange,symbol) DO NOTHING",
                        [(exchange, symbol, rows[0].source) for symbol in missing],
                    )
                    cur.execute("SELECT id,symbol FROM instrument WHERE exchange=%s AND symbol=ANY(%s)", (exchange, missing))
                    for instrument_id, symbol in cur.fetchall():
                        ids[(exchange, symbol)] = instrument_id

            observations = []
            canonicals = []
            for bar in rows:
                instrument_id = ids[(bar.exchange, bar.symbol)]
                observations.append((
                    instrument_id,bar.trade_date,bar.source,bar.source_priority,bar.pre_close,bar.open,bar.high,bar.low,
                    bar.close,bar.volume_shares,bar.turnover_cny,bar.pct_change,bar.pe_ratio,bar.trade_status,bar.is_st,
                    raw_artifact_id,json.dumps(bar.extra),
                ))
                canonicals.append((
                    instrument_id,bar.trade_date,bar.pre_close,bar.open,bar.high,bar.low,bar.close,bar.volume_shares,
                    bar.turnover_cny,bar.pct_change,bar.pe_ratio,bar.trade_status,bar.is_st,bar.source,bar.source_priority,
                ))
            cur.executemany(observation_sql, observations)
            cur.executemany(canonical_sql, canonicals)
        return len(rows)

    def record_early_history_gap(self, instrument_id: int, symbol: str, list_date: date, first_bar_date: date, source: str) -> None:
        gap_days = (first_bar_date - list_date).days
        if gap_days <= 7:
            return
        details = json.dumps({"symbol": symbol, "list_date": str(list_date), "first_bar_date": str(first_bar_date), "gap_days": gap_days})
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_quality_issue(instrument_id,issue_type,severity,source,details)
                SELECT %s,'EARLY_HISTORY_GAP','WARN',%s,%s::jsonb
                WHERE NOT EXISTS (
                    SELECT 1 FROM data_quality_issue WHERE instrument_id=%s AND issue_type='EARLY_HISTORY_GAP' AND source=%s AND status='OPEN'
                )
                """,
                (instrument_id,source,details,instrument_id,source),
            )
