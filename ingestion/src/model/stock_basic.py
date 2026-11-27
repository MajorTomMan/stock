from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from decimal import Decimal
import json
from typing import get_args


@dataclass(slots=True)
class StockBasic:
    code: str
    name: str
    source: str
    ipo_date: date | None = None
    out_date: date | None = None


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