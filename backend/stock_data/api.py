"""Read-only HTTP API for canonical Shenzhen A-share market data.

Run from backend/: python -m uvicorn stock_data.api:app --host 127.0.0.1 --port 8000
"""
from datetime import date, timedelta
import re

from fastapi import FastAPI, HTTPException, Query

from .config import Settings
from .database import Database
from .queries import MarketQueries


app = FastAPI(title="Stock Market Data", version="0.2.0")
queries = MarketQueries(Database(Settings.from_env().database_url))


def _symbol(value: str) -> str:
    symbol = value.upper().strip()
    if not re.fullmatch(r"\d{6}(?:\.SZ)?", symbol):
        raise HTTPException(status_code=422, detail="Expected six-digit SZSE symbol, e.g. 000001.SZ")
    return symbol[:6]


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
    result = queries.get_instrument(_symbol(symbol))
    if result is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return result


@app.get("/api/instruments/{symbol}/daily")
def instrument_daily(symbol: str,
                     start: date | None = None,
                     end: date | None = None,
                     limit: int = Query(default=250, ge=1, le=5000),
                     published_only: bool = False):
    """Newest N bars within the optional date window, returned oldest-to-newest.

    Historical BAOSTOCK backfill remains UNREVIEWED in this publication phase.
    """
    code = _symbol(symbol)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start must not be after end")
    if queries.get_instrument(code) is None:
        raise HTTPException(status_code=404, detail="Instrument not found")

    rows = queries.get_daily(code, start, end, limit + 1, published_only=published_only)
    has_more = len(rows) > limit
    rows = rows[:limit]  # SQL order is newest first
    rows.reverse()       # chart-friendly ascending dates
    next_end = rows[0]["trade_date"] - timedelta(days=1) if has_more and rows else None
    return {
        "symbol": code + ".SZ",
        "published_only": published_only,
        "count": len(rows),
        "has_more": has_more,
        "next_end": next_end,
        "bars": rows,
    }


@app.get("/api/market/overview")
def market_overview(limit: int = Query(default=30, ge=1, le=100)):
    """Latest date present in our database; it may not be today's market date."""
    return queries.market_overview(limit)


@app.get("/api/quality/publications")
def quality_publications(limit: int = Query(default=30, ge=1, le=100)):
    return {"items": queries.publication_status(limit)}


@app.get("/api/quality/issues")
def quality_issues(limit: int = Query(default=50, ge=1, le=200),
                   status: str = Query(default="OPEN", pattern="^(OPEN|RESOLVED)$")):
    return {"items": queries.quality_issues(limit, status)}


@app.get("/api/market/published-overview")
def published_overview(limit: int = Query(default=30, ge=1, le=100)):
    """Latest explicitly published official SZSE daily snapshot, or empty if none."""
    return queries.published_overview(limit)
