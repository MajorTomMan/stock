from datetime import date
from decimal import Decimal
from dataclasses import dataclass, fields


@dataclass(slots=True)
class DailyBar:
    """日线行情公共数据模型"""

    # ===== 基础信息 =====
    trade_date: date             # 交易日期
    symbol: str                  # 股票代码，例如 sh.600000
    source : str                 # 数据来源，例如 BaoStock
    # ===== 价格信息 =====
    open: Decimal | None = None       # 开盘价，元/股
    high: Decimal | None = None       # 最高价，元/股
    low: Decimal | None = None        # 最低价，元/股
    close: Decimal | None = None      # 收盘价，元/股
    pre_close: Decimal | None = None  # 前收盘价，元/股

    # ===== 成交信息 =====
    volume: int | None = None         # 成交量，单位：股
    amount: Decimal | None = None     # 成交金额，单位：元（CNY）
    pct_change: Decimal | None = None # 涨跌幅，单位：%


    def to_fields(self):
        pass



    def transformation(self):
        """遍历模型字段，将日期转换为字符串并返回键值对。"""
        for field in fields(self):
            if field.name == "trade_date":
                yield field.name, self.trade_date.strftime("%Y-%m-%d")
            else:
                yield field.name, getattr(self, field.name)