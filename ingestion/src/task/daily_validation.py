"""Validate parsed daily bars without changing or discarding source records."""

from dataclasses import dataclass
from typing import Iterable

from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


@dataclass(slots=True)
class InvalidDailyBar:
    bar: BaoDailyBar
    reasons: list[str]


@dataclass(slots=True)
class DailyValidationResult:
    valid: list[BaoDailyBar]
    invalid: list[InvalidDailyBar]


def validate_daily_bars(bars: Iterable[BaoDailyBar]) -> DailyValidationResult:
    """Separate basic OHLC/volume anomalies; duplicates are another stage's job."""
    valid: list[BaoDailyBar] = []
    invalid: list[InvalidDailyBar] = []

    for bar in bars:
        reasons: list[str] = []
        for field in ("open", "high", "low", "close", "pre_close"):
            price = getattr(bar, field)
            if price is not None and price <= 0:
                reasons.append(f"{field} must be positive")

        for field in ("volume", "amount"):
            value = getattr(bar, field)
            if value is not None and value < 0:
                reasons.append(f"{field} must be non-negative")

        if bar.low is not None and bar.high is not None:
            if bar.low > bar.high:
                reasons.append("low exceeds high")
            for field in ("open", "close"):
                price = getattr(bar, field)
                if price is not None and not bar.low <= price <= bar.high:
                    reasons.append(f"{field} outside low/high range")

        if reasons:
            invalid.append(InvalidDailyBar(bar=bar, reasons=reasons))
        else:
            valid.append(bar)

    return DailyValidationResult(valid=valid, invalid=invalid)
