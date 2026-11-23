from prefect import task

from ingestion.src.constant.redis import RedisStream
from ingestion.src.handler.handler_factory import HandlerFactory
from ingestion.src.pulisher.impl.redis_stream_publisher import RedisStreamPublisher
from ingestion.src.source.bao.model.daily_bar import DailyBar
from ingestion.src.source.stock_source_factory import StockSourceFactory
from ingestion.src.task.stock_task import StockTask


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
def deduplicate_daily(source:str,bars:list[DailyBar]):    
    handler = HandlerFactory.get(source=source,handler_type="deduplicate")
    result = handler.deduplicate(bars)
    print("去重前:", len(bars))
    print("去重后:", len(result))
    return result

@task
def validate_daily(source:str,bars:list[DailyBar]):
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
async def stock_daily_publish(data:list):
    if not isinstance(data,list):
        raise TypeError("只接受List格式")
    publisher = RedisStreamPublisher(stream_name=RedisStream.Name)
    temp = []
    for d in data:
        temp.append(DailyBar.to_dict(d))
    return await publisher.publish(temp)