


from ingestion.src.handler.deduplicate_handler import DeduplicateHandler
from ingestion.src.source.bao.model.daily_bar import BaoDailyBar



class BaoDeduplicateHandler(DeduplicateHandler):
    def __init__(self, config):
        self.config = config
    # 去重依赖如下几个字段来实现去重
    # (source, symbol, trade_date, adjust_flag)
    @staticmethod
    def deduplicate(data:list[BaoDailyBar]):
        seen = set()
        unique_bars = []
        for bar in data:
            key = (
                bar.source,
                bar.symbol,
                bar.trade_date,
                bar.adjust_flag
            )
            if key not in seen:
                    seen.add(key)
                    unique_bars.append(bar)

        return unique_bars
        