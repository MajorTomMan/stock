

from prefect.schedules import Cron

from ingestion.src.task.stock_task import StockTask
from ingestion.tests.test_checkpoint import stock_daily_flow


tasks = [
StockTask(
    task_id="bao-daily-001",
    source="bao",
    dataset="daily",
    params={
        "code": "sh.600000",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }),
    StockTask(
    task_id="bao-daily-002",
    source="bao",
    dataset="daily",
    params={
        "code": "sz.000001",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    })
]

if __name__ == "__main__":
    stock_daily_flow.serve(
        name="stock-daily-local",
        parameters={"tasks": tasks},
        schedules=[
            Cron(
                "*/4 * * * *",
                timezone="Asia/Shanghai"
            )
        ],
        global_limit=1,
    )