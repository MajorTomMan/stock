from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class StockTask(Generic[T]):
    task_id: str
    source: str
    dataset: str

    params: dict[str, Any] = field(default_factory=dict)
    data: T | None = None
    extra: dict[str, Any] = field(default_factory=dict)