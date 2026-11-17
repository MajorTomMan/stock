


from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.utils.redis_util import RedisUtil
from ingestion.src.pulisher.message_publisher import MessagePublisher


class RedisStreamPublisher(MessagePublisher):
    def __init__(self, stream_name):
        self.stream_name = stream_name
        self.redis_client = RedisUtil(password="4r$P9v&fL!sXj8@Qz2yD")
    async def publish(self, message: dict):
        # 将消息发布到 Redis Stream
        if isinstance(message, list):
            for msg in message:
                await self.redis_client.stream_add(
                    stream=self.stream_name,
                    fields=msg,
                )
        else:
            await self.redis_client.stream_add(
                stream=self.stream_name,
                fields=message,
            )