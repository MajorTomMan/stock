from abc import ABC, abstractmethod
from collections.abc import Sequence

from ingestion.src.model.daily_bar import DailyBar

class StockSource(ABC):

    @abstractmethod
    def fetch_daily(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> Sequence[DailyBar]:
        pass