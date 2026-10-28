
from prefect import flow, task


@task
def fetch(symbol: str):
    print(f"正在抓取股票 {symbol}")
    return {
        "symbol": symbol,
        "close": "12.50",
        "volume": "1000"
    }


@task
def normalize(data: dict):
    return {
        "symbol": data["symbol"],
        "close": float(data["close"]),
        "volume_shares": int(data["volume"]) * 100
    }


@task
def save(data: dict):
    print(f"准备保存: {data}")
    return len(data)


@flow(name="stock-daily")
def stock_flow(symbol: str):
    raw = fetch(symbol)
    normalized = normalize(raw)
    return save(normalized)


if __name__ == "__main__":
    stock_flow("000001")
