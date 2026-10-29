from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from dataclasses import fields as dataclass_fields


@dataclass(slots=True)
class BaoDailyBar:
    # 基础信息
    date: date
    code: str

    # OHLC
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    pre_close: Decimal | None = None

    # 成交信息
    volume: int | None = None
    amount: Decimal | None = None
    turnover_rate: Decimal | None = None
    pct_change: Decimal | None = None

    # 交易状态
    adjust_flag: int = 3
    trade_status: int | None = None
    is_st: bool | None = None

    # 估值指标
    pe_ttm: Decimal | None = None
    pb_mrq: Decimal | None = None
    ps_ttm: Decimal | None = None
    pcf_ncf_ttm: Decimal | None = None

    fields = {
    "pre_close": "preclose",
    "turnover_rate": "turn",
    "pct_change": "pctChg",
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
            cls.fields.get(f.name, f.name)
            for f in dataclass_fields(cls)
        )