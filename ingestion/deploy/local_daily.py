from ingestion.src.workflow.daily_flow import stock_daily_flow
from ingestion.src.task.stock_task import StockTask

tasks = [
    StockTask(
        task_id="bao-daily-001",
        source="bao",
        dataset="daily",
        params={
            "code": "sh.600000",
            "start_date": "2023-01-01",
            "end_date": "2023-01-05",
        },
    ),
]

if __name__ == "__main__":
    stock_daily_flow.serve(
        name="stock-daily-local",
        parameters={"tasks": tasks},
    )