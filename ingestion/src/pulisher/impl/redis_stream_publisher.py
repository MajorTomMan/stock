


from ingestion.src.utils.redis_util import RedisUtil
from ingestion.src.pulisher.message_publisher import MessagePublisher
import json

class RedisStreamPublisher(MessagePublisher):
    def __init__(self, stream_name):
        self.stream_name = stream_name
        self.redis_client = RedisUtil(password="4r$P9v&fL!sXj8@Qz2yD")
    async def publish(self, messages:  list):
        # 将消息发布到 Redis Stream
        if  not isinstance(messages,list):
            raise TypeError("发布数据必须是列表形式")
        messages_ids = []
        msgs = self.transform(messages)
        for msg in msgs:
            msg_id = await self.redis_client.stream_add(stream=self.stream_name,fields=msg)
            messages_ids.append(msg_id)
        return messages_ids
    
    def transform(self,messages:list):
        temps = []
        for msg in messages:
            if isinstance(msg,str):
                try:
                    result = json.loads(msg)
                    temps.append(result)
                except:
                    print(f"数据必须是Json格式:{msg}")
            else:
                temps.append(msg)
        return temps