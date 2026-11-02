



from ingestion.src.pulisher.message_publisher import MessagePublisher


class RedisStreamPublisher(MessagePublisher):
    def __init__(self, redis_client, stream_name):
        self.redis_client = redis_client
        self.stream_name = stream_name

    def publish(self, message):
        # 将消息发布到 Redis Stream
        self.redis_client.xadd(self.stream_name, message)