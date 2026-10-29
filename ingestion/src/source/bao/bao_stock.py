import baostock as bs
import pandas as pd

from ingestion.src.source.bao.model.daily_bar import BaoDailyBar


class BaoStock:
    def __init__(self):
        pass

    def login(self, username: str, password: str):
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
        return rs

    def format_data(self, data):
        data_list = []
        while (data.error_code == '0') & data.next():
            data_list.append(data.get_row_data())
        df = pd.DataFrame(data_list, columns=data.fields)
        return df