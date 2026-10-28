from abc import ABC, abstractmethod
from datetime import date

from ..models import DailyBar


class DailyMarketProvider(ABC):
    name: str
    priority: int

    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        raise NotImplementedError
