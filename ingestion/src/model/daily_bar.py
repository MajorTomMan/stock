"""Common, provider-independent fields for one daily market observation."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(slots=True)
class DailyBar:
    trade_date: date
    symbol: str

    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    pre_close: Decimal | None = None

    volume: int | None = None  # shares
    amount: Decimal | None = None  # CNY
    pct_change: Decimal | None = None
