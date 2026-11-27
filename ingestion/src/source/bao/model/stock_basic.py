from dataclasses import dataclass

from ingestion.src.model.stock_basic import StockBasic


@dataclass(slots=True)
class BaoStockBasic(StockBasic):
    source: str = "bao"
    security_type: int | None = None
    status: int | None = None


    