from dataclasses import dataclass
from datetime import date


@dataclass
class DailyBar:
    symbol: str
    trade_date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None