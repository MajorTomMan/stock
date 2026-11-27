from pandas import DataFrame
from prefect import flow, task

from ingestion.src.source.bao.bao_stock import BaoStock

bao = BaoStock()
@task
def get_all_stocks_with_date(date: str):
    return bao.fetch_stock_list(date)


def get_all_stock_with_basic(code:str = None):
    return bao.fetch_stock_basic(code)


@flow(name="test-stock-list")
def main():
    stocks:list[DataFrame] = get_all_stocks_with_date("2026-11-24")
    for stock in stocks:
        code = stock.get("code")
        if code:
            result = get_all_stock_with_basic()
            if result:
                print(result)
                print(result.get("code_name").get(0))
                print("----------------------------")

if __name__ == "__main__":
    main()