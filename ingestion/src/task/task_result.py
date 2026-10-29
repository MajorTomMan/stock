from dataclasses import dataclass
from typing import Generic, TypeVar

from ingestion.src.task.stock_task import StockTask

T = TypeVar("T")


@dataclass
class TaskResult(Generic[T]):
    task: StockTask[T]
    stage: str
    data: T
