



from ingestion.src.model.daily_bar import DailyBar


class DeduplicateHandler:
    def __init__(self, config):
        self.config = config
    # 去重依赖如下几个字段来实现去重
    # (source, symbol, trade_date, adjust_flag)
    @staticmethod
    def deduplicate(data:list[DailyBar]):
        pass
