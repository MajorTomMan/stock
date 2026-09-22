from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class InstrumentRecord:
    exchange: str
    symbol: str
    current_name: str | None = None
    full_name: str | None = None
    english_name: str | None = None
    security_type: str = "STOCK"
    board: str | None = None
    list_date: date | None = None
    delist_date: date | None = None
    status: str = "UNKNOWN"
    registered_address: str | None = None
    region: str | None = None
    province: str | None = None
    city: str | None = None
    industry: str | None = None
    website: str | None = None
    source: str | None = None


@dataclass
class NameChangeRecord:
    exchange: str
    symbol: str
    effective_date: date
    before_name: str | None
    after_name: str | None
    source: str


@dataclass
class DailyBar:
    exchange: str
    symbol: str
    trade_date: date
    source: str
    source_priority: int
    pre_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume_shares: int | None = None
    turnover_cny: float | None = None
    pct_change: float | None = None
    pe_ratio: float | None = None
    trade_status: int | None = None
    is_st: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)
