"""Small BaoStock → preview Prefect example (run as a module)."""

from datetime import date
from decimal import Decimal

from prefect import flow, task

from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.pulisher.impl.redis_stream_publisher import RedisStreamPublisher
from ingestion.src.source.bao.bao_stock import BaoStock
from ingestion.src.source.bao.handler.deduplicate_handler import BaoDeduplicateHandler
from ingestion.src.source.bao.handler.validate_handler import BaoValidateHandler
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


from ingestion.src.constant.redis import RedisStream
from ingestion.src.task.stock_task import StockTask

tasks = [
StockTask(
    task_id="bao-daily-001",
    source="bao",
    dataset="daily",
    params={
        "symbol": "sh.600000",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }),
    StockTask(
    task_id="bao-daily-002",
    source="bao",
    dataset="daily",
    params={
        "symbol": "sz.000001",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    })
]



@task(retries=3, retry_delay_seconds=[30, 60, 120])
def fetch_daily(task:StockTask):
    params = task.params
    if params:
        source = task.source
        symbol = params.get("symbol")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        if source == "bao":
            return BaoStock().fetch_daily(symbol,start_date,end_date)
        return []
@task
def deduplicate_daily(bars:list[BaoDailyBar]):    
    handler = BaoDeduplicateHandler(config={})

    result = handler.deduplicate(bars)

    print("去重前:", len(bars))
    print("去重后:", len(result))
    return result

@task
def validate_daily(bars):
    valid_bars = []
    handler = BaoValidateHandler(config={})

    for bar in bars:
        try:
            handler.validate(bar)
            valid_bars.append(bar)
        except ValueError as e:
            print(f"校验失败: {e}")
    print("校验前:", len(bars))
    print("校验后:", len(valid_bars))
    return valid_bars

@task
def preview_daily(bars):
    print(f"Fetched {len(bars)} daily bars.")
    for bar in bars[:5]:
        #print(bar)
        pass


@task
async def stock_daily_publish(data:list):
    if not isinstance(data,list):
        raise TypeError("只接受List格式")
    publisher = RedisStreamPublisher(stream_name=RedisStream.Name)
    temp = []
    for d in data:
        temp.append(DailyBar.to_dict(d))
    return await publisher.publish(temp)

@flow(name="bao-stock-daily")
def stock_daily_flow(tasks: list[StockTask]):
    for stock_task in tasks:
        try:
            data = fetch_daily.submit(task=stock_task).result()
            deduplicate = deduplicate_daily.submit(data)
            validate = validate_daily.submit(deduplicate)

            ids = stock_daily_publish.submit(validate).result()

            print(f"任务完成: {stock_task.task_id}, 发布 {len(ids)} 条")

        except Exception as exc:
            print(f"任务失败: {stock_task.task_id}, 原因: {exc}")
            continue

if __name__ == "__main__":
    stock_daily_flow(tasks=tasks)
