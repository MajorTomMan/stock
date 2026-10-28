from dataclasses import dataclass
from typing import Generic, TypeVar

from ingestion.src.task import StockTask

T = TypeVar("T")


@dataclass
class TaskResult(Generic[T]):
    task: StockTask
    stage: str
    data: T