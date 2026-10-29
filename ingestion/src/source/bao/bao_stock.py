import baostock as bs
import pandas as pd

from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


class BaoStock:
    def __init__(self):
        pass

    def login_with_name(self, username: str, password: str):
        return bs.login(username=username, password=password)

    def login_status(self):
        return bs.is_logged_in()

    def login(self):
        return bs.login()

    
    def logout(self):
        return bs.logout()


    def query_daily_k_data(self, code: str, start_date: str, end_date: str):
        fields = BaoDailyBar.to_fields()
        rs = bs.query_history_k_data_plus(code=code, fields=fields, start_date=start_date, end_date=end_date)
        print(f"BaoStock: query_daily_k_data {code} {start_date} {end_date} {rs.error_code} {rs.error_msg}")
        return rs

    def format_data(self, rs):
        if rs.error_code != "0":
            raise RuntimeError(
                f"BaoStock: {rs.error_code} {rs.error_msg}"
            )

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())

        return pd.DataFrame(rows, columns=rs.fields)

    def parse_daily_bars(self, df: pd.DataFrame) -> list[BaoDailyBar]:
        bars = []
        for _, row in df.iterrows():
            bar = BaoDailyBar(
                date=pd.to_datetime(row["date"]).date(),
                code=row["code"],
                open=pd.to_numeric(row["open"], errors="coerce"),
                high=pd.to_numeric(row["high"], errors="coerce"),
                low=pd.to_numeric(row["low"], errors="coerce"),
                close=pd.to_numeric(row["close"], errors="coerce"),
                pre_close=pd.to_numeric(row.get("preclose"), errors="coerce"),
                volume=pd.to_numeric(row.get("volume"), errors="coerce"),
                amount=pd.to_numeric(row.get("amount"), errors="coerce"),
                turnover_rate=pd.to_numeric(row.get("turn"), errors="coerce"),
                pct_change=pd.to_numeric(row.get("pctChg"), errors="coerce"),
                adjust_flag=int(row.get("adjustflag", 3)),
                trade_status=int(row.get("tradestatus")) if row.get("tradestatus") else None,
                is_st=row.get("isST") == "1" if row.get("isST") else None,
                pe_ttm=pd.to_numeric(row.get("peTTM"), errors="coerce"),
                pb_mrq=pd.to_numeric(row.get("pbMRQ"), errors="coerce"),
                ps_ttm=pd.to_numeric(row.get("psTTM"), errors="coerce"),
                pcf_ncf_ttm=pd.to_numeric(row.get("pcfNcfTTM"), errors="coerce"),
            )
            bars.append(bar)
        return bars