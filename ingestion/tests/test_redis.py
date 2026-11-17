import asyncio
import pytest
from ingestion.src.utils.redis_util import RedisUtil

redis_util = RedisUtil(password="4r$P9v&fL!sXj8@Qz2yD")



async def test_redis_util():

    print(await redis_util.ping())


async def test_publish():

        message_id = await redis_util.stream_add(
            stream="stock:daily",
            fields={
                "source": "bao",
                "symbol": "sh.600000",
                "trade_date": "2023-01-03",
                "close": "10.50",
            },
        )
        print("消息 ID:", message_id)
        return message_id


async def test_consume():
    data = await redis_util.stream_read(stream="stock:daily", count=10)
    print("消费数据:", data)


async def test_ack(id):
    await redis_util.stream_ack(
        stream="stock:daily",
        group="stock_group",
        message_id=id,
    )


async def test_delete(id):
    await redis_util.stream_xdel(
        stream="stock:daily",
        message_id=id,
    )

async def test_main():
    await test_redis_util()
    message_id = await test_publish()
    await test_consume()
    await test_ack(message_id)
    await test_delete(message_id)
    await test_close()

async def test_close():
    await redis_util.close()


if __name__ == "__main__":
     asyncio.run(test_main())




