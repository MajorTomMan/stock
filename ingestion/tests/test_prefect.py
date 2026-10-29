"""Small BaoStock → validation → preview Prefect example (run as a module)."""

from prefect import flow, task

from ingestion.src.source.bao.bao_stock import BaoStock
from ingestion.src.task.daily_validation import DailyValidationResult, validate_daily_bars


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
def validate_daily(bars) -> DailyValidationResult:
    return validate_daily_bars(bars)


@task
def preview_daily(result: DailyValidationResult):
    print(f"Fetched {len(result.valid) + len(result.invalid)} daily bars: "
          f"{len(result.valid)} valid, {len(result.invalid)} invalid")
    for bar in result.valid[:5]:
        print(bar)
    for issue in result.invalid[:5]:
        print(f"Invalid {issue.bar.code} {issue.bar.date}: {', '.join(issue.reasons)}")


@flow(name="bao-stock-daily")
def stock_daily_flow():
    data = fetch_daily.submit("sh.600000", "2023-01-01", "2023-12-31")
    checked = validate_daily.submit(data)
    preview_daily.submit(checked).result()


if __name__ == "__main__":
    stock_daily_flow()
