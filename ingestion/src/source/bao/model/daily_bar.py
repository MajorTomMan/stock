from dataclasses import dataclass, field, fields
from decimal import Decimal

from ingestion.src.constant.dict import STOCK_FIELDS
from ingestion.src.model.daily_bar import DailyBar


@dataclass(slots=True)
class BaoDailyBar(DailyBar):
    """BaoStock 日线行情数据模型"""
    source: str = field(default="bao", init=False)
    # ===== 交易指标 =====
    turnover_rate: Decimal | None = None  # 换手率，单位：%
    adjust_flag: int = 3                  # 复权类型：1 后复权、2 前复权、3 不复权

    # ===== 交易状态 =====
    trade_status: int | None = None       # 交易状态：1 正常交易、0 停牌
    is_st: bool | None = None             # 是否为 ST 股票

    # ===== 估值指标 =====
    pe_ttm: Decimal | None = None         # 市盈率 TTM，最近12个月滚动市盈率
    pb_mrq: Decimal | None = None         # 市净率 MRQ，基于最近报告期净资产
    ps_ttm: Decimal | None = None         # 市销率 TTM，基于最近12个月营业收入
    pcf_ncf_ttm: Decimal | None = None    # 市现率 TTM，基于最近12个月净现金流

    @classmethod
    def to_fields(cls) -> str:
        mapping = STOCK_FIELDS["bao"]
        basic = STOCK_FIELDS["basic"]

        return ",".join(
            mapping.get(f.name, basic.get(f.name, f.name))
            for f in fields(cls)
            if f.name != "source"
        )