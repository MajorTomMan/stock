
import redis.asyncio as redis
from redis.exceptions import ResponseError


class RedisUtil:
    """异步 Redis 工具类，封装连接和 Stream 操作。"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 16379,
        username: str | None = None,
        password: str | None = "4r$P9v&fL!sXj8@Qz2yD",
        db: int = 0,
    ):
        self.client = redis.Redis(
            host=host,
            port=port,
            username=username,
            password=password,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=10,
        )

    async def ping(self) -> bool:
        """检查 Redis 是否可以正常访问。"""
        return await self.client.ping()

    async def close(self):
        """关闭 Redis 客户端，释放连接池资源。"""
        await self.client.aclose()

    async def __aenter__(self):
        # 支持 async with 自动管理客户端生命周期
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def stream_add(
        self,
        stream: str,
        fields: dict,
    ) -> str:
        """
        向 Redis Stream 添加一条消息。

        stream: Stream 名称，例如 stock:daily
        fields: 消息字段和值，值必须是 Redis 支持的标量类型

        返回：Redis 生成的消息 ID，例如 1690000000000-0
        """
        return await self.client.xadd(
            name=stream,
            fields=fields,
        )

    
    async def stream_read(
        self,
        stream: str,
        stream_id:int,
        count: int = 10,
    ):
        """
        从 Redis Stream 读取消息。

        stream: Stream 名称，例如 stock:daily
        count: 单次最多读取的消息数

        返回：包含消息 ID 和字段的列表
        """
        return await self.client.xread(
            streams={stream: stream_id},
            count=count,
            block=1000,  # 没有消息时最多等待 1 秒
        )

    
    async def stream_create_group(
        self,
        stream: str,
        group: str,
    ):
        """创建消费者组，允许读取已有消息。"""
        try:
            await self.client.xgroup_create(
                name=stream,
                groupname=group,
                id="0",
                mkstream=True,  # Stream 不存在时自动创建
            )
        except ResponseError as exc:
            # 消费者组已经存在时无需重复创建
            if "BUSYGROUP" not in str(exc):
                raise

    async def stream_read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
    ):
        """
        通过消费者组读取新消息。

        group: 消费者组名称
        consumer: 消费者名称
        count: 单次最多读取的消息数

        block=1000：没有消息时最多等待 1 秒
        ">"：只读取尚未分配给其他消费者的新消息
        """
        return await self.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=1000,
        )

    async def stream_xlen(
        self,
        stream: str,
    ) -> int:
        """获取 Stream 中的消息数量。"""
        return await self.client.xlen(stream)

    async def stream_xdel(
        self,
        stream: str,
        message_id: str,
    ) -> int:
        """删除 Stream 中指定 ID 的消息。"""
        return await self.client.xdel(stream, message_id)


    async def stream_ack(
        self,
        stream: str,
        group: str,
        message_id: str,
    ) -> int:
        """
        确认消息已经处理完成。

        消费者成功处理并持久化数据后，再调用 XACK。
        返回成功确认的消息数量。
        """
        return await self.client.xack(
            stream,
            group,
            message_id,
        )


