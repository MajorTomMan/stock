from datetime import date, datetime
from decimal import Decimal
from dataclasses import asdict, dataclass, fields
import json
import decimal
from typing import get_args
@dataclass(slots=True)
class DailyBar:
    """日线行情公共数据模型"""

    # ===== 基础信息 =====
    trade_date: date | None = None            # 交易日期
    symbol: str | None = None            # 股票代码，例如 sh.600000
    source : str | None = None                 # 数据来源，例如 BaoStock
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
                
    @classmethod
    def to_dict(cls, instance):
        return asdict(instance)

    @classmethod
    def from_dict(cls, data: dict):
        entity = cls(**data)
        print("原始数据:", data)
        print("创建的实体:", entity)
        for field in fields(cls):
            if field.name not in data:
                continue
            value = data[field.name]
            if field.type is Decimal or Decimal in get_args(field.type):
                if value is not None:
                    value = Decimal(value)
            elif field.type is date or date in get_args(field.type):
                if value is not None and isinstance(value, str):
                    value = datetime.strptime(value, "%Y-%m-%d").date()
            else:
                # 其他类型不做处理
                pass
            setattr(entity, field.name, value)
        print("转换后的实体:", entity)
        return entity
    
    @classmethod
    def to_json(cls, instance) -> str:
        return json.dumps(cls.to_dict(instance), default=str)

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        return cls.from_dict(data)