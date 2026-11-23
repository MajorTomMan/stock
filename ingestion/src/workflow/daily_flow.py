
from prefect import flow

from ingestion.src.task.stock_task import StockTask
from ingestion.src.workflow.daily_tasks import *



@flow(name="stock-daily")
def stock_daily_flow(tasks: list[StockTask]):
    for task in tasks:
        try:
            source = task.source
            data = fetch_daily.submit(task=task).result()
            deduplicate = deduplicate_daily.submit(source,data)
            validate = validate_daily.submit(source,deduplicate)

            ids = stock_daily_publish.submit(validate).result()

            print(f"任务完成: {task.task_id}, 发布 {len(ids)} 条")

        except Exception as exc:
            print(f"任务失败: {task.task_id}, 原因: {exc}")
            continue