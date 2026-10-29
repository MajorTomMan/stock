from ingestion.src.source.bao.bao_stock import BaoStock


if __name__ == "__main__":

    bao = BaoStock()

    bao.login()

    data = bao.query_daily_k_data(code="sh.600000", start_date="2025-10-13",end_date="2025-10-17")
    result = bao.format_data(data)
    print(result)
    bars = bao.parse_daily_bars(result)
    for bar in bars:
        print(bar)
    