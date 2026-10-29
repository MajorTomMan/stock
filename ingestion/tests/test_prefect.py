from prefect import flow, task


@task(retries=2, retry_delay_seconds=5)
def fetch(exchange: str):
    raise RuntimeError("深交所接口异常")
    return f"{exchange} 采集成功"


@flow
def stock_flow():
    futures = {
        "SSE": fetch.submit("SSE"),
        "SZSE": fetch.submit("SZSE"),
    }

    # 等两条分支分别结束，不因其中一条失败而提前抛异常
    for future in futures.values():
        future.wait()

    failed = [
        name
        for name, future in futures.items()
        if not future.state.is_completed()
    ]

    if failed:
        raise RuntimeError(f"采集失败的数据源: {failed}")

    return {
        name: future.result()
        for name, future in futures.items()
    }


if __name__ == "__main__":
    stock_flow()