# Python Backend · 只读市场 API

由现有 FastAPI 路由和 SQL 查询逻辑迁移而来，**不启动爬虫**。依赖 `ingestion/` 中可以编辑安装的 `stock_data` 包读取 PostgreSQL。

## 启动

仓库根目录：

```bash
cd ingestion
docker compose up -d
python -m pip install -e .
python -m stock_data.cli migrate
cd ..

python -m pip install -r backend/python/requirements.txt
python -m uvicorn market_api.app:app --app-dir backend/python --host 127.0.0.1 --port 8000
```

已有接口的 URL 和返回形状保持不变：

- `GET /health`
- `GET /api/instruments`
- `GET /api/instruments/{symbol}`
- `GET /api/instruments/{symbol}/daily`
- `GET /api/market/overview`
- `GET /api/quality/daily?date=2025-09-01`

文档：http://127.0.0.1:8000/docs。

当前 API 没有鉴权，只用于本机开发；它返回数据库中已采集的历史行情，并非实时市场数据。

未来 Spring Boot 交易核心放在 `backend/java/`，不要求这套市场读 API 重写成 Java。
