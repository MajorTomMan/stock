"""Read-only HTTP API for canonical Shenzhen and Shanghai A-share market data.

Run from backend/: python -m uvicorn stock_data.api:app --host 127.0.0.1 --port 8000
"""
from datetime import date, timedelta
import re

from fastapi import FastAPI, HTTPException, Query

from .config import Settings
from .database import Database
from .queries import MarketQueries


app = FastAPI(title="Stock Market Data", version="0.3.0")
queries = MarketQueries(Database(Settings.from_env().database_url))


def _symbol(value: str) -> tuple[str, str | None]:
    text = value.upper().strip()
    match = re.fullmatch(r"(\d{6})(?:\.(SZ|SH|SZSE|SSE))?", text)
    if not match:
        raise HTTPException(status_code=422, detail="Expected six-digit A-share symbol, e.g. 000001.SZ or 600000.SH")
    suffix = match.group(2)
    exchange = None
    if suffix in {"SZ", "SZSE"}:
        exchange = "SZSE"
    elif suffix in {"SH", "SSE"}:
        exchange = "SSE"
    return match.group(1), exchange


def _display_symbol(symbol: str, exchange: str) -> str:
    return symbol + (".SH" if exchange == "SSE" else ".SZ")


@app.get("/health")
def health():
    try:
        queries.healthcheck()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok"}


@app.get("/api/instruments")
def list_instruments(q: str = Query(default="", max_length=128),
                     limit: int = Query(default=30, ge=1, le=100),
                     offset: int = Query(default=0, ge=0)):
    rows = queries.search_instruments(q.strip(), limit, offset)
    return {"items": rows, "count": len(rows), "limit": limit, "offset": offset}


@app.get("/api/instruments/{symbol}")
def instrument_detail(symbol: str):
    code, exchange = _symbol(symbol)
    result = queries.get_instrument(code, exchange)
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


@app.get("/api/instruments/{symbol}/daily")
def instrument_daily(symbol: str,
                     start: date | None = None,
                     end: date | None = None,
                     limit: int = Query(default=250, ge=1, le=5000)):
    """Newest N bars within the optional date window, returned oldest-to-newest."""
    code, requested_exchange = _symbol(symbol)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    instrument = queries.get_instrument(code, requested_exchange)
    if instrument is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    exchange = instrument["exchange"]
    rows = queries.get_daily(code, start, end, limit + 1, exchange)
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    next_end = rows[0]["trade_date"] - timedelta(days=1) if has_more and rows else None
    return {
        "symbol": _display_symbol(code, exchange),
        "exchange": exchange,
        "count": len(rows),
        "has_more": has_more,
        "next_end": next_end,
        "bars": rows,
    }


@app.get("/api/market/overview")
def market_overview(limit: int = Query(default=30, ge=1, le=100)):
    """Latest date present in our database; it may not be today's market date."""
    return queries.market_overview(limit)
