from abc import ABC, abstractmethod
from collections.abc import Sequence

from ingestion.src.model.daily_bar import DailyBar


class MessagePublisher(ABC):
    """消息发布器抽象接口。"""

    """
        发布一批行情数据。

        Args:
            data: 已完成去重、校验的行情数据。

        Returns:
            str: 消息发布成功后的消息 ID。

        Raises:
            Exception: 发布失败时抛出异常。
    """
    @abstractmethod
    async def publish(self, data: Sequence[DailyBar]) -> str:
        pass
