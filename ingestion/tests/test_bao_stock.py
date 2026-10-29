from ingestion.src.source.bao.bao_stock import BaoStock


if __name__ == "__main__":

    bao = BaoStock()

    bao.login()

    data = bao.query_daily_k_data(code="sh.600000", start_date="2020-01-01", end_date="2020-12-31")
    result = bao.format_data(data)
    print(result)