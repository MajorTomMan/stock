
import json
from datetime import date
from decimal import Decimal

from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


# 测试 1：字典恢复基础类型
def test_from_dict_basic():
    data = {
        "trade_date": "2023-01-03",
        "code": "sh.600000",
        "source": "bao",
        "open": "7.2700",
        "close": "7.2300",
        "volume": 25892521,
    }

    bar = DailyBar.from_dict(data)

    assert isinstance(bar.trade_date, date)
    assert isinstance(bar.open, Decimal)
    assert isinstance(bar.close, Decimal)
    assert isinstance(bar.volume, int)

    assert bar.close == Decimal("7.2300")


# 测试 2：正确处理 None
def test_from_dict_nullable():
    data = {
        "trade_date": "2023-01-03",
        "code": "sh.600000",
        "source": "bao",
        "open": None,
        "close": "0.0000",
    }

    bar = DailyBar.from_dict(data)

    assert bar.open is None
    assert bar.high is None
    assert bar.close == Decimal("0.0000")
    assert isinstance(bar.close, Decimal)


# 测试 3：子类继承与字段恢复
def test_bao_from_dict():
    data = {
        "trade_date": "2023-01-03",
        "code": "sh.600000",
        "source": "bao",
        "close": "7.2300",
        "turnover_rate": "0.088200",
        "adjust_flag": 3,
        "is_st": False,
        "pe_ttm": "4.086661",
    }

    bar = BaoDailyBar.from_dict(data)

    assert isinstance(bar, BaoDailyBar)
    assert isinstance(bar.trade_date, date)
    assert isinstance(bar.close, Decimal)
    assert isinstance(bar.turnover_rate, Decimal)
    assert isinstance(bar.pe_ttm, Decimal)
    assert bar.adjust_flag == 3
    assert bar.is_st is False


# 测试 4：to_dict 返回真正的字典
def test_to_dict():
    bar = DailyBar(
        trade_date=date(2023, 1, 3),
        code="sh.600000",
        source="bao",
        close=Decimal("7.2300"),
    )

    data = DailyBar.to_dict(bar)

    assert isinstance(data, dict)
    assert data["trade_date"] == date(2023, 1, 3)
    assert data["close"] == Decimal("7.2300")
    assert data["source"] == "bao"


# 测试 5：完整 JSON 往返转换
def test_json_roundtrip():
    original = BaoDailyBar(
        trade_date=date(2023, 1, 3),
        code="sh.600000",
        source="bao",
        close=Decimal("7.2300"),
        turnover_rate=Decimal("0.088200"),
        is_st=False,
        adjust_flag=3,
    )

    json_str = BaoDailyBar.to_json(original)

    # 必须是合法 JSON
    assert isinstance(json_str, str)
    assert isinstance(json.loads(json_str), dict)

    restored = BaoDailyBar.from_json(json_str)

    assert isinstance(restored, BaoDailyBar)
    assert isinstance(restored.trade_date, date)
    assert isinstance(restored.close, Decimal)
    assert isinstance(restored.turnover_rate, Decimal)
    assert restored.is_st is False
    assert restored == original



def test_from_dict_date_object():
    data = {
        "trade_date": date(2023, 1, 3),
        "code": "sh.600000",
        "source": "bao",
        "close": "7.2300",
    }

    bar = DailyBar.from_dict(data)

    assert bar.trade_date == date(2023, 1, 3)
    assert isinstance(bar.close, Decimal)


def test_from_dict_null_date():
    data = {
        "trade_date": None,
        "code": "sh.600000",
        "source": "bao",
    }

    bar = DailyBar.from_dict(data)

    assert bar.trade_date is None


def test_json_roundtrip():
    original = BaoDailyBar(
        trade_date=date(2023, 1, 3),
        code="sh.600000",
        source="bao",
        close=Decimal("7.2300"),
        turnover_rate=Decimal("0.088200"),
        adjust_flag=3,
    )

    json_str = BaoDailyBar.to_json(original)
    restored = BaoDailyBar.from_json(json_str)

    assert isinstance(restored, BaoDailyBar)
    assert isinstance(restored.trade_date, date)
    assert isinstance(restored.close, Decimal)
    assert isinstance(restored.turnover_rate, Decimal)
    assert restored == original



if __name__ == "__main__":
    test_from_dict_basic()
    test_from_dict_nullable()
    test_bao_from_dict()
    test_to_dict()
    test_json_roundtrip()
    test_from_dict_date_object()
    test_from_dict_null_date()
    test_json_roundtrip()