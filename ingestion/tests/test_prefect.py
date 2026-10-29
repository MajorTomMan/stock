"""Small BaoStock → preview Prefect example (run as a module)."""

from prefect import flow, task

from ingestion.src.source.bao.bao_stock import BaoStock


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
def preview_daily(bars):
    print(f"Fetched {len(bars)} daily bars.")
    for bar in bars[:5]:
        print(bar)


@flow(name="bao-stock-daily")
def stock_daily_flow():
    data = fetch_daily.submit("sh.600000", "2023-01-01", "2023-12-31")
    preview_daily.submit(data).result()


if __name__ == "__main__":
    stock_daily_flow()
