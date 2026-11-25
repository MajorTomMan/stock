"""Small BaoStock → preview Prefect example (run as a module)."""


import asyncio
from datetime import date, timedelta
import json

from prefect import flow, task

from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.pulisher.impl.redis_stream_publisher import RedisStreamPublisher
from ingestion.src.handler.handler_factory import HandlerFactory
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar
from ingestion.src.source.stock_source_factory import StockSourceFactory

from ingestion.src.constant.redis import RedisStream
from ingestion.src.task.stock_task import StockTask
from ingestion.src.utils.redis_util import RedisUtil

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
    factory = StockSourceFactory()
    params = task.params
    if params:
        source = task.source
        symbol = params.get("symbol")
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        instance = factory.get(source=source)
        results = instance.fetch_daily(symbol=symbol,start_date=start_date,end_date=end_date)
        return results
@task
def deduplicate_daily(source:str,bars:list[BaoDailyBar]):    
    handler = HandlerFactory.get(source=source,handler_type="deduplicate")
    result = handler.deduplicate(bars)
    print("去重前:", len(bars))
    print("去重后:", len(result))
    return result

@task
def validate_daily(source:str,bars:list[BaoDailyBar]):
    valid_bars = []
    handler = HandlerFactory.get(source=source,handler_type="validate")

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
async def load_checkpoint(key: str) -> dict | None:
    if not key:
        raise ValueError("业务键不能为空")

    async with RedisUtil() as redis:
        result = await redis.get(key)

        if result is None:
            return None

        return json.loads(result)

def generateKey(task:StockTask):
    return f"stock:checkpoint:{task.source}:{task.dataset}:{task.params["symbol"]}:{task.params.get("adjust_flag", 3)}"
    
@task
async def save_checkpoint(key: str, checkpoint: dict) -> None:
    if not key:
        raise ValueError("业务键不能为空")

    async with RedisUtil() as redis:
        await redis.set(
            key,
            json.dumps(checkpoint, ensure_ascii=False)
        )

@task
async def stock_daily_publish(data:list):
    if not isinstance(data,list):
        raise TypeError("只接受List格式")
    publisher = RedisStreamPublisher(stream_name=RedisStream.Name)
    temp = []
    for d in data:
        temp.append(DailyBar.to_dict(d))
    return await publisher.publish(temp)


def generateCheckPoint(task:StockTask):
    return {
        "start_date": task.params["start_date"],
        "end_date": task.params["end_date"],
    }


@flow(name="bao-stock-daily")
async def stock_daily_flow(tasks: list[StockTask]):
    for task in tasks:
        try:
            key = generateKey(task)
            source = task.source
            cached_checkpoint = await load_checkpoint(key)
            if cached_checkpoint:
                print(f"{task.params["symbol"]}的检查点为:{cached_checkpoint}")
                cached_start_date = cached_checkpoint.get("start_date")
                cached_end_date = cached_checkpoint.get("end_date")
                if cached_start_date:
                    # 计算新的时间区间
                    task.params.update(
                        calculate_date_range(cached_checkpoint)
                    )
                    if task.params["start_date"] > task.params["end_date"]:
                        continue
            else:
                print(f"{task.params["symbol"]}的检查点为空")
            data = fetch_daily.submit(task=task).result()
            deduplicate = deduplicate_daily.submit(source,data)
            validate = validate_daily.submit(source,deduplicate)
            ids = stock_daily_publish.submit(validate).result()
            checkpoint = generateCheckPoint(task=task)
            await save_checkpoint(key,checkpoint)
            print(f"任务完成: {task.task_id}, 发布 {len(ids)} 条")

        except Exception as exc:
            print(f"任务失败: {task.task_id}, 原因: {exc}")
            continue


def calculate_date_range(
    checkpoint: dict,
    interval_days: int = 90
) -> dict:

    start_date = (
        date.fromisoformat(checkpoint["end_date"])
        + timedelta(days=1)
    )

    end_date = min(
        start_date + timedelta(days=interval_days - 1),
        date.today()
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@task
def main():
    asyncio.run(stock_daily_flow(tasks=tasks))

if __name__ == "__main__":
    main()
