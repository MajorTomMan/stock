from ingestion.src.source.bao.bao_stock import BaoStock
from ingestion.src.source.stock_source import StockSource
class StockSourceFactory:

    def __init__(self):
        self.sources = {
            "bao": BaoStock,
        }

    def get(self, source: str) -> StockSource:
        source_class = self.sources.get(source)

        if source_class is None:
            raise ValueError(f"不存在该类数据源: {source}")

        return source_class()