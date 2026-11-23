


from ingestion.src.model.daily_bar import DailyBar
from ingestion.src.utils.redis_util import RedisUtil
from ingestion.src.pulisher.message_publisher import MessagePublisher
import json

class RedisStreamPublisher(MessagePublisher):
    def __init__(self, stream_name):
        self.stream_name = stream_name
        self.redis_client = RedisUtil(password="4r$P9v&fL!sXj8@Qz2yD")
    async def publish(self, message:  list  | dict | str):
        # 将消息发布到 Redis Stream
        message_id = ""
        if isinstance(message, list):
            for msg in message:
                result = self.transform(msg)
                message_id = await self.redis_client.stream_add(
                    stream=self.stream_name,
                    fields=result,
                )
        else:
            message_id = await self.redis_client.stream_add(
                stream=self.stream_name,
                fields=message,
            )
        self.redis_client.close()
        return message_id

    def transform(self,message):
        if isinstance(message,str):
            try:
                msg = json.loads(message)
                return msg
            except:
                raise TypeError("数据传递只能使用json格式")
        return message