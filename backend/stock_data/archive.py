from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .database import Database


SCHEMA = pa.schema([
    ("exchange", pa.string()),
    ("symbol", pa.string()),
    ("trade_date", pa.date32()),
    ("pre_close", pa.float64()),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume_shares", pa.int64()),
    ("turnover_cny", pa.float64()),
    ("pct_change", pa.float64()),
    ("pe_ratio", pa.float64()),
    ("trade_status", pa.int16()),
    ("is_st", pa.bool_()),
    ("selected_source", pa.string()),
    ("source_priority", pa.int16()),
])


def _float(value):
    return None if value is None else float(value)


def export_market_daily_year(
    db: Database,
    year: int,
    output_dir: Path,
    *,
    exchange: str = "SZSE",
    batch_rows: int = 50_000,
) -> dict:
    exchange = exchange.upper()
    if exchange not in {"SZSE", "SSE"}:
        raise ValueError("--exchange must be SZSE or SSE")
    if year < 1990 or year > 2100:
        raise ValueError("--year must be between 1990 and 2100")
    if batch_rows < 1:
        raise ValueError("--batch-rows must be >= 1")

    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    target_dir = output_dir / "market_daily" / exchange.lower()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{year}.parquet"

    sql = """
        SELECT i.exchange,i.symbol,md.trade_date,md.pre_close,md.open,md.high,md.low,md.close,
               md.volume_shares,md.turnover_cny,md.pct_change,md.pe_ratio,md.trade_status,md.is_st,
               md.selected_source,md.source_priority
        FROM market_daily md
        JOIN instrument i ON i.id=md.instrument_id
        WHERE i.exchange=%s AND md.trade_date >= %s AND md.trade_date < %s
        ORDER BY i.symbol,md.trade_date
    """

    rows_written = 0
    arrow_bytes = 0
    writer = None
    try:
        with db.connect() as conn:
            with conn.cursor(name="market_daily_parquet_export") as cur:
                cur.execute(sql, (exchange, start, end))
                while True:
                    rows = cur.fetchmany(batch_rows)
                    if not rows:
                        break
                    records = [{
                        "exchange": row[0],
                        "symbol": row[1],
                        "trade_date": row[2],
                        "pre_close": _float(row[3]),
                        "open": _float(row[4]),
                        "high": _float(row[5]),
                        "low": _float(row[6]),
                        "close": _float(row[7]),
                        "volume_shares": row[8],
                        "turnover_cny": _float(row[9]),
                        "pct_change": _float(row[10]),
                        "pe_ratio": _float(row[11]),
                        "trade_status": row[12],
                        "is_st": row[13],
                        "selected_source": row[14],
                        "source_priority": row[15],
                    } for row in rows]
                    table = pa.Table.from_pylist(records, schema=SCHEMA)
                    arrow_bytes += table.nbytes
                    if writer is None:
                        writer = pq.ParquetWriter(
                            target,
                            SCHEMA,
                            compression="zstd",
                            use_dictionary=["exchange", "symbol", "selected_source"],
                        )
                    writer.write_table(table)
                    rows_written += len(records)
    finally:
        if writer is not None:
            writer.close()

    if rows_written == 0:
        target.unlink(missing_ok=True)

    file_bytes = target.stat().st_size if target.exists() else 0
    return {
        "exchange": exchange,
        "year": year,
        "rows": rows_written,
        "file": str(target),
        "parquet_bytes": file_bytes,
        "parquet_mib": round(file_bytes / 1024 / 1024, 3),
        "arrow_uncompressed_mib": round(arrow_bytes / 1024 / 1024, 3),
        "compression_ratio": round(arrow_bytes / file_bytes, 2) if file_bytes else None,
        "bytes_per_row": round(file_bytes / rows_written, 2) if rows_written else None,
        "compression": "zstd",
        "note": "This is canonical market_daily only; source observations and PostgreSQL indexes are not included.",
    }
