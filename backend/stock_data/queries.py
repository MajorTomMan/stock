"""SQL-only read model; never queries external market-data providers."""
from datetime import date

from psycopg.rows import dict_row

from .database import Database


class MarketQueries:
    def __init__(self, db: Database):
        self.db = db

    def healthcheck(self) -> None:
        with self.db.connect() as conn:
            conn.execute("SELECT 1")

    def search_instruments(self, q: str, limit: int, offset: int) -> list[dict]:
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT exchange, symbol, current_name, board, status, list_date, delist_date
                FROM instrument
                WHERE exchange='SZSE' AND security_type='STOCK'
                  AND (
                    %s = '' OR strpos(symbol, %s) > 0
                    OR strpos(lower(coalesce(current_name, '')), lower(%s)) > 0
                  )
                ORDER BY CASE WHEN symbol = %s THEN 0 ELSE 1 END, symbol
                LIMIT %s OFFSET %s
                """,
                (q, q, q, q.removesuffix(".SZ").upper(), limit, offset),
            )
            return cur.fetchall()

    def get_instrument(self, symbol: str) -> dict | None:
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, exchange, symbol, current_name, full_name, board,
                       industry, status, list_date, delist_date, province, city
                FROM instrument
                WHERE exchange='SZSE' AND symbol=%s AND security_type='STOCK'
                """,
                (symbol,),
            )
            return cur.fetchone()

    def get_daily(self, symbol: str, start: date | None, end: date | None, limit: int) -> list[dict]:
        sql = """
            SELECT d.trade_date, d.pre_close, d.open, d.high, d.low, d.close,
                   d.volume_shares, d.turnover_cny, d.pct_change, d.pe_ratio,
                   d.trade_status, d.is_st, d.selected_source
            FROM market_daily AS d
            JOIN instrument AS i ON i.id=d.instrument_id
            WHERE i.exchange='SZSE' AND i.symbol=%s
        """
        params: list = [symbol]
        if start is not None:
            sql += " AND d.trade_date >= %s"
            params.append(start)
        if end is not None:
            sql += " AND d.trade_date <= %s"
            params.append(end)
        sql += " ORDER BY d.trade_date DESC LIMIT %s"
        params.append(limit)
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def market_overview(self, limit: int) -> dict:
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT MAX(trade_date) FROM market_daily")
            as_of = cur.fetchone()["max"]
            if as_of is None:
                return {"as_of": None, "items": [], "count": 0}
            cur.execute(
                """
                SELECT i.symbol, i.current_name, d.trade_date, d.close,
                       d.pct_change, d.volume_shares, d.turnover_cny, d.selected_source
                FROM market_daily d
                JOIN instrument i ON i.id = d.instrument_id
                WHERE i.exchange='SZSE' AND i.security_type='STOCK'
                  AND d.trade_date=%s
                ORDER BY d.turnover_cny DESC NULLS LAST, i.symbol
                LIMIT %s
                """,
                (as_of, limit),
            )
            rows = cur.fetchall()
            return {"as_of": as_of, "count": len(rows), "items": rows}
