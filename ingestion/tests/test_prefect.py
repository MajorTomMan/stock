"""Small BaoStock → preview Prefect example (run as a module)."""

from datetime import date
from decimal import Decimal

from prefect import flow, task

from ingestion.src.source.bao.bao_stock import BaoStock
from ingestion.src.source.bao.handler.deduplicate_handler import BaoDeduplicateHandler
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar



test_bars = [
    # A：正常记录
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 3),
        close=Decimal("10.50"),
        adjust_flag=3
    ),

    # B：与 A 完全重复
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 3),
        close=Decimal("10.50"),
        adjust_flag=3
    ),

    # C：与 A 业务键相同，但收盘价不同
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 3),
        close=Decimal("10.80"),
        adjust_flag=3
    ),

    # D：不同日期
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 4),
        close=Decimal("10.60"),
        adjust_flag=3
    ),

    # E：不同复权方式
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 3),
        close=Decimal("10.50"),
        adjust_flag=1
    ),

    # F：不同股票
    BaoDailyBar(
        symbol="sz.000001",
        trade_date=date(2023, 1, 3),
        close=Decimal("12.00"),
        adjust_flag=3
    ),

    # G：与 D 重复
    BaoDailyBar(
        symbol="sh.600000",
        trade_date=date(2023, 1, 4),
        close=Decimal("10.60"),
        adjust_flag=3
    ),
]


@task
def fetch_daily(code: str, start: str, end: str):
    bao = BaoStock()
    bao.login()
    try:
        result = bao.query_daily_k_data(code=code, start_date=start, end_date=end)
        return bao.parse_daily_bars(bao.format_data(result))
    finally:
        bao.logout()



@task
def deduplicate_daily(bars):    
    handler = deduplicate_handler(config={})

    result = handler.deduplicate(test_bars)

    print("去重前:", len(test_bars))
    print("去重后:", len(result))

    assert len(result) == 4
    assert result[0].close == Decimal("10.50")



@task
def preview_daily(bars):
    print(f"Fetched {len(bars)} daily bars.")
    for bar in bars[:5]:
        print(bar)


@flow(name="bao-stock-daily")
def stock_daily_flow():
    data = fetch_daily.submit("sh.600000", "2023-01-01", "2023-12-31")
    deduplicate = deduplicate_daily.submit(data)
    preview_daily.submit(deduplicate).result()


if __name__ == "__main__":
    stock_daily_flow()
