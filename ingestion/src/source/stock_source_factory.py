from abc import ABC
from ingestion.src.source.bao.bao_stock import BaoStock
from ingestion.src.source.stock_source import StockSource

class StockSourceFactory(ABC):

    def __init__(self):
        self.instances = {}
        self.instances["bao"] = BaoStock()



    def get(self,source:str) -> StockSource:
        instance = self.instances.get(source)
        if instance is None:
            raise ValueError(f"不存在该类数据源:{source}")
        return instance