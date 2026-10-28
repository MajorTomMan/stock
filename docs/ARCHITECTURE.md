# Stock · 分层与依赖约定

## 三个业务层

```text
stock/
├── ingestion/                    # Python · 市场数据采集与存储
│   ├── src/                      # 源码物理目录；安装后包名为 stock_data
│   │   ├── providers/            # SSE/SZSE/BaoStock 数据源
│   │   ├── ingestion.py          # 采集任务及断点
│   │   ├── database.py           # market 数据库操作
│   │   ├── models.py             # 市场数据模型
│   │   ├── migrations.py         # 当前数据库迁移
│   │   ├── quality.py            # 数据质量检查
│   │   ├── archive.py            # Parquet
│   │   └── cli.py                # CLI 采集入口
│   ├── tests/
│   ├── pyproject.toml            # 可安装的 stock_data 包
│   └── docker-compose.yml        # 本地开发 PG 环境，不是部署层
├── backend/
│   ├── python/
│   │   └── market_api/
│   │       ├── app.py            # FastAPI HTTP 路由
│   │       └── queries.py        # 只读市场 SQL
│   └── java/
│       └── README.md             # M2 Spring Boot 交易领域预留
├── frontend/                     # Vue 3 + Vite
└── docs/
```

## 边界

- `ingestion/src/`（安装后逻辑包为 `stock_data`）：持有市场数据模型、provider、任务、质量、迁移和 market 数据库访问。**不得依赖 FastAPI 或 Java 服务**。
- `backend/python/market_api`：只读市场 API 与查询 SQL；只依赖 `stock_data` 包，不执行采集任务。
- `backend/java`：M2 再增加 Spring Boot；负责模拟账户、资金、订单、成交和持仓的一致性，不维护 Python 的行情采集代码。
- `frontend`：通过 HTTP 消费 API，不连接 PostgreSQL、不请求采集来源。
- 不建立空部署层，也不为了拆目录提前引入服务发现、消息总线等基础设施。

```text
SSE / SZSE / BaoStock
          │
          ▼
  ingestion/ (Python)
          │ 写入 market 数据
          ▼
       PostgreSQL
          │
      ┌───┴────────────────┐
      ▼                    ▼
 backend/python        backend/java (M2)
   FastAPI             Spring Boot
      │                    │
      └─────────┬──────────┘
                ▼
            frontend/
```

## 数据一致性

1. 市场来源记录写入 `market_daily_observation`，对外行情选择结果写入 `market_daily`；重构不修改 schema。
2. 前端、历史回测和模拟盘最终共用 canonical 行情。
3. Python 写 market 数据；未来 Java 独立写 trading 业务数据，不共同拥有一张业务表的写权限。
4. 模拟撮合必须使用当时可获知的数据，遵守市场规则。
5. 本次只重组仓库，不引入数据库重建、数据清理或导入重跑。

## 本地数据保护

旧版本可能在 `backend/data/` 保存了 Git 忽略的原始 XLSX、JSON 和归档文件。Git 提交只移动**已跟踪源码**，不会自动移动这些实际数据。

如果 `ingestion/data/` 尚不存在，且确实有旧 `backend/data/`，可在仓库根目录手动执行：

```bash
if [ -d backend/data ] && [ ! -e ingestion/data ]; then
  mv backend/data ingestion/data
fi
```

若目标目录已存在，先人工核对文件再合并，**不要强制覆盖**。这会让在 `ingestion/` 工作目录运行的现有 CLI 继续访问 `./data/raw` 和 `./data/archive`。

移动了 `backend/docker-compose.yml` 到 `ingestion/docker-compose.yml`，但显式使用 `name: backend`，以复用原 Compose 项目名、`stock-postgres` 容器和 `backend_postgres18_data` 命名卷（前提是旧环境使用默认 Compose 项目名）。用户若曾自定义 `COMPOSE_PROJECT_NAME` 或 `-p`，需要继续使用同一个值。

**不要执行** `docker compose down -v`、`docker volume prune` 或 `git clean -fdx`。

## 下一阶段

M1 不启动 Java 服务。M2 再定义 Java 交易模型与接口契约、建立 Spring Boot 工程，Python 采集与 FastAPI 市场接口保持独立。
