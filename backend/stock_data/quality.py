"""Read-only spot checks against existing canonical and source observations.

No additional tables, publication states, or third-party requests.
"""
from datetime import date
from decimal import Decimal

from psycopg.rows import dict_row

from .database import Database


class DailyQuality:
    def __init__(self, db: Database):
        self.db = db

    def inspect(self, trade_date: date) -> dict:
        with self.db.connect() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT i.symbol, d.open, d.high, d.low, d.close,
                       d.volume_shares, d.turnover_cny, d.selected_source,
                       sz.instrument_id AS official_present, sz.close AS szse_close, bs.close AS baostock_close
                FROM market_daily d
                JOIN instrument i ON i.id=d.instrument_id
                LEFT JOIN market_daily_observation sz
                  ON sz.instrument_id=d.instrument_id AND sz.trade_date=d.trade_date AND sz.source='SZSE'
                LEFT JOIN market_daily_observation bs
                  ON bs.instrument_id=d.instrument_id AND bs.trade_date=d.trade_date AND bs.source='BAOSTOCK'
                WHERE i.exchange='SZSE' AND i.security_type='STOCK' AND d.trade_date=%s
                ORDER BY i.symbol
                """,
                (trade_date,),
            )
            rows = cur.fetchall()
            cur.execute(
                """
                SELECT row_count FROM ingestion_run
                WHERE provider='SZSE' AND dataset='stock_snapshot'
                  AND requested_from=%s AND requested_to=%s AND status='SUCCESS'
                ORDER BY id DESC LIMIT 1
                """,
                (trade_date, trade_date),
            )
            latest = cur.fetchone()
            expected_szse_rows = latest["row_count"] if latest else None

        issues = []
        szse_count = sum(row["official_present"] is not None for row in rows)
        if not rows:
            issues.append({"symbol": None, "type": "NO_DATA",
                           "detail": "数据库中没有这一天的行情；可能是休市，也可能尚未采集"})
        if expected_szse_rows is not None and expected_szse_rows != szse_count:
            issues.append({"symbol": None, "type": "SNAPSHOT_COUNT_MISMATCH",
                           "detail": f"最近一次官方导入 {expected_szse_rows} 条，当前官方日线 {szse_count} 条"})
        for row in rows:
            symbol = row["symbol"]
            prices = {key: row[key] for key in ("open", "high", "low", "close") if row[key] is not None}
            if any(value <= 0 for value in prices.values()):
                issues.append({"symbol": symbol, "type": "NON_POSITIVE_PRICE", "detail": "存在非正价格"})
            if "high" in prices and any(prices["high"] < value for key, value in prices.items() if key != "high"):
                issues.append({"symbol": symbol, "type": "INVALID_HIGH", "detail": "最高价低于其他价格"})
            if "low" in prices and any(prices["low"] > value for key, value in prices.items() if key != "low"):
                issues.append({"symbol": symbol, "type": "INVALID_LOW", "detail": "最低价高于其他价格"})
            if any(row[key] is not None and row[key] < 0 for key in ("volume_shares", "turnover_cny")):
                issues.append({"symbol": symbol, "type": "NEGATIVE_VOLUME_OR_TURNOVER",
                               "detail": "成交量或成交额为负"})
            if row["szse_close"] is not None and row["baostock_close"] is not None:
                if Decimal(row["szse_close"]) != Decimal(row["baostock_close"]):
                    issues.append({"symbol": symbol, "type": "SOURCE_CLOSE_DIFF",
                                   "detail": f"SZSE={row['szse_close']} BaoStock={row['baostock_close']}"})
        return {"date": trade_date.isoformat(), "bars": len(rows),
                "official_bars": szse_count, "latest_official_import_rows": expected_szse_rows,
                "issue_count": len(issues), "issues": issues[:100],
                "truncated": len(issues) > 100,
                "note": "只检查已有行情；未建立交易日历，不能据此认定休市或历史数据完整"}
