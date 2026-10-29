from prefect import flow, task
from ingestion.src.source.bao.bao_stock import BaoStock

@task
def fetch_daily(code: str, start: str, end: str):
        bao = BaoStock()
        bao.login()
        data = bao.query_daily_k_data(code=code, start_date=start, end_date=end)
        result = bao.format_data(data)
        bars = bao.parse_daily_bars(result)
        bao.logout()
        return bars


@task
def preview_daily(bars):
     print(bars)


@flow(name="bao-stock-daily")
def stock_daily_flow():
    data = fetch_daily.submit("sh.600000", "2023-01-01", "2023-12-31")
    preview_daily.submit(data)


if __name__ == "__main__":
    stock_daily_flow()