from decimal import Decimal

import baostock as bs
import pandas as pd

from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


def _decimal(value: object) -> Decimal | None:
    """Preserve source precision and distinguish missing values from zero."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return None
    return Decimal(text)


def _integer(value: object) -> int | None:
    number = _decimal(value)
    if number is None:
        return None
    if number != number.to_integral_value():
        raise ValueError(f"Expected integer value, got {value!r}")
    return int(number)


class BaoStock:
    def login_with_name(self, username: str, password: str):
        return bs.login(username=username, password=password)

    def login_status(self):
        return bs.is_logged_in()

    def login(self):
        result = bs.login()
        if result.error_code != "0":
            raise RuntimeError(f"BaoStock login failed: {result.error_code} {result.error_msg}")
        return result

    def logout(self):
        return bs.logout()

    def query_daily_k_data(self, code: str, start_date: str, end_date: str):
        fields = BaoDailyBar.to_fields()
        rs = bs.query_history_k_data_plus(
            code=code, fields=fields, start_date=start_date, end_date=end_date
        )
        print(f"BaoStock: query_daily_k_data {code} {start_date} {end_date} {rs.error_code} {rs.error_msg}")
        return rs

    def format_data(self, rs):
        if rs.error_code != "0":
            raise RuntimeError(f"BaoStock: {rs.error_code} {rs.error_msg}")

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=rs.fields)

    def parse_daily_bars(self, df: pd.DataFrame) -> list[BaoDailyBar]:
        bars = []
        for _, row in df.iterrows():
            adjust_flag = _integer(row.get("adjustflag"))
            raw_st = str(row.get("isST", "")).strip()
            bar = BaoDailyBar(
                date=pd.to_datetime(row["date"]).date(),
                code=row["code"],
                open=_decimal(row["open"]),
                high=_decimal(row["high"]),
                low=_decimal(row["low"]),
                close=_decimal(row["close"]),
                pre_close=_decimal(row.get("preclose")),
                volume=_integer(row.get("volume")),
                amount=_decimal(row.get("amount")),
                turnover_rate=_decimal(row.get("turn")),
                pct_change=_decimal(row.get("pctChg")),
                adjust_flag=3 if adjust_flag is None else adjust_flag,
                trade_status=_integer(row.get("tradestatus")),
                is_st=raw_st == "1" if raw_st in {"0", "1"} else None,
                pe_ttm=_decimal(row.get("peTTM")),
                pb_mrq=_decimal(row.get("pbMRQ")),
                ps_ttm=_decimal(row.get("psTTM")),
                pcf_ncf_ttm=_decimal(row.get("pcfNcfTTM")),
            )
            bars.append(bar)
        return bars
