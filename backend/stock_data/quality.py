"""Conservative gates for daily SZSE snapshots.

A passing report confirms basic structural plausibility, not that the entire
exchange history or every security's daily bar has been verified.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Check:
    issue_type: str
    severity: str
    details: dict[str, Any]
    instrument_id: int | None = None


def audit_snapshot(trade_date: date, bars: list[dict], expected_count: int,
                   imported_count: int, *, min_coverage: float = 0.65) -> dict:
    """Validate the persisted source observations for a single successful import.

    An observed eligible security need not trade on every date; the coverage
    ratio is a conservative *snapshot-level* sanity gate, not a gap detector.
    """
    if not (0 < min_coverage <= 1):
        raise ValueError("min_coverage must be in (0, 1]")
    blockers: list[Check] = []
    warnings: list[Check] = []
    count = len(bars)
    if not count:
        blockers.append(Check("SNAPSHOT_EMPTY", "ERROR", {"date": str(trade_date)}))
    if count != imported_count:
        blockers.append(Check("SNAPSHOT_SOURCE_COUNT", "ERROR", {
            "observed": count, "latest_import_count": imported_count,
        }))
    if expected_count < 30:
        blockers.append(Check("SNAPSHOT_BASELINE_UNAVAILABLE", "ERROR", {
            "eligible": expected_count, "reason": "Fewer than 30 eligible, dated securities in current master data",
        }))
    elif count < expected_count * min_coverage:
        blockers.append(Check("SNAPSHOT_LOW_COVERAGE", "ERROR", {
            "observed": count, "eligible": expected_count, "min_coverage": min_coverage,
        }))

    for bar in bars:
        invalid: list[str] = []
        prices = {k: bar.get(k) for k in ("open", "high", "low", "close")}
        non_null = {k: Decimal(str(v)) for k, v in prices.items() if v is not None}
        if any(v <= 0 for v in non_null.values()):
            invalid.append("non_positive_price")
        if len(non_null) == 4:
            if non_null["high"] < max(non_null["open"], non_null["close"], non_null["low"]):
                invalid.append("high_less_than_other_price")
            if non_null["low"] > min(non_null["open"], non_null["close"], non_null["high"]):
                invalid.append("low_greater_than_other_price")
        for col in ("volume_shares", "turnover_cny"):
            value = bar.get(col)
            if value is not None and value < 0:
                invalid.append(f"negative_{col}")
        if invalid:
            blockers.append(Check("OHLC_INVALID", "ERROR", {
                "symbol": bar["symbol"], "reason": invalid,
            }, bar["instrument_id"]))

        other_close = bar.get("baostock_close")
        if other_close is not None and bar.get("close") is not None and other_close != bar["close"]:
            warnings.append(Check("SOURCE_CLOSE_MISMATCH", "WARN", {
                "symbol": bar["symbol"],
                "szse_close": str(bar["close"]),
                "baostock_close": str(other_close),
            }, bar["instrument_id"]))

    return {
        "date": trade_date.isoformat(),
        "status": "BLOCKED" if blockers else "STAGED",
        "observed_count": count,
        "eligible_count": expected_count,
        "imported_count": imported_count,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
    }
