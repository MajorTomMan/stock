# Stock · A 股市场数据平台

当前阶段：**深市历史行情采集、只读查询和股票网站**。项目暂不提供交易或实时行情。

## 目录

```text
stock/
├── frontend/                # Vite 股票目录、搜索、历史 K 线、成交量与行情概览
├── backend/
│   ├── stock_data/
│   │   ├── providers/       # BaoStock / 深交所原始数据采集
│   │   ├── ingestion.py     # 冷启动、增量任务和断点续跑
│   │   ├── database.py      # PostgreSQL 存取与来源选择
│   │   ├── migrations.py    # 数据表版本
│   │   ├── models.py        # 数据模型
│   │   ├── cli.py           # 数据采集命令入口
│   │   ├── queries.py       # 只读行情查询
│   │   └── api.py           # FastAPI 接口
│   ├── tests/               # Python 测试
│   ├── docker-compose.yml  # PostgreSQL 18
│   └── README.md           # 安装、回填、查询 API 完整操作说明
└── .github/workflows/      # Python 语法与单元测试
```

## 本地快速启动

```bash
cd backend
docker compose up -d
python -m pip install -r requirements.txt
python -m stock_data.cli migrate
python -m uvicorn stock_data.api:app --host 127.0.0.1 --port 8000
```

API 文档：http://127.0.0.1:8000/docs

另开一个终端启动网站：

```bash
cd frontend
npm install
npm run dev
```

网站：http://127.0.0.1:5173（自动代理本机 8000 端口的 `/api` 请求）

前端功能与当前边界详见 [frontend/README.md](frontend/README.md)。

已有数据库无需重建：执行 `migrate` 只会应用尚未执行的表结构版本。**不要使用 `docker compose down -v` 或 `git clean -fdx` 清理运行目录**；PostgreSQL volume 和 `backend/data/raw/` 保存实际业务数据。

历史回填、SZSE 每日快照、参数与常见问题见 [backend/README.md](backend/README.md)。

## 数据范围与边界

BaoStock 提供未复权历史日线；SZSE 提供证券主数据及可取得的官方日快照。来源观察值保存在 `market_daily_observation`，最终选择结果在 `market_daily`。本项目当前仅支持深市股票数据，尚未完成全量历史覆盖与交易日历质量校验。
