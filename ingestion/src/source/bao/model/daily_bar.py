"""BaoStock-specific daily fields and request-field names."""

from dataclasses import dataclass, fields as dataclass_fields
from decimal import Decimal
from typing import ClassVar

from ingestion.src.model.daily_bar import DailyBar


@dataclass(slots=True)
class BaoDailyBar(DailyBar):
    turnover_rate: Decimal | None = None
    adjust_flag: int = 3
    trade_status: int | None = None
    is_st: bool | None = None

    pe_ttm: Decimal | None = None
    pb_mrq: Decimal | None = None
    ps_ttm: Decimal | None = None
    pcf_ncf_ttm: Decimal | None = None

    # Keep source API names here, not in the provider-independent model.
    source_fields: ClassVar[dict[str, str]] = {
        "trade_date": "date",
        "symbol": "code",
        "pre_close": "preclose",
        "pct_change": "pctChg",
        "turnover_rate": "turn",
        "adjust_flag": "adjustflag",
        "trade_status": "tradestatus",
        "is_st": "isST",
        "pe_ttm": "peTTM",
        "pb_mrq": "pbMRQ",
        "ps_ttm": "psTTM",
        "pcf_ncf_ttm": "pcfNcfTTM",
    }

    @classmethod
    def to_fields(cls) -> str:
        return ",".join(
            cls.source_fields.get(field.name, field.name)
            for field in dataclass_fields(cls)
        )
