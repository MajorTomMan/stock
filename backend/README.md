# Backend · 深市日线数据

当前阶段仅包含：SZSE 证券主数据与官方日快照、BaoStock 未复权历史回填、PostgreSQL 数据存储以及只读行情 API。**不包含**实时行情、交易或回测功能。

## 项目职责

| 路径 | 作用 |
| --- | --- |
| `stock_data/providers/` | 对接 BaoStock 与深交所，转换为统一模型 |
| `stock_data/ingestion.py` | 主数据同步、日快照、按股票分批回填 |
| `stock_data/database.py` | 数据存取、采集执行记录、数据质量问题 |
| `stock_data/migrations.py` | 数据表结构版本；由 CLI 自动执行 |
| `stock_data/queries.py`、`api.py` | 只读数据库、提供 HTTP API |
| `tests/` | 不依赖数据库或网络的单元测试 |
| `data/raw/szse/` | 下载的原始 XLSX（本机生成，已被 Git 忽略） |

`market_daily_observation` 保存各来源原始规范化事实；`market_daily` 选择对外使用的日线。SZSE 来源优先级为 10，BaoStock 为 50，同一天的 BaoStock 记录不会覆盖已选中的 SZSE 记录。价格保留未复权形式；成交量为**股**，成交额为**元**；停牌记录中的 NULL 与 0 保持区别。

## 启动（已有数据库无需删除或重新初始化）

在 `backend/` 目录运行：

```bash
docker compose up -d
python -m pip install -r requirements.txt
python -m stock_data.cli migrate
```

默认 PostgreSQL 连接 URL 为 `postgresql://major:majortom@127.0.0.1:10007/stock`。可通过 `DATABASE_URL` 覆盖；`RAW_DATA_DIR` 默认为 `./data/raw`，`HTTP_TIMEOUT_SECONDS` 默认为 40。参考 `.env.example`；CLI 不会自动读取该文件，需要使用环境变量或自行加载。

**重要：**现有 compose 的宿主机端口映射是 `10007:5432`，可能监听所有网络接口。API 示例默认仅监听本机；如需在不受信任的网络环境使用数据库，应单独限制数据库端口访问。不要执行 `docker compose down -v`、`docker volume prune` 或 `git clean -fdx`，避免丢失 PostgreSQL 数据卷或本机原始 XLSX。

## 采集命令

首次使用时同步深交所主数据：

```bash
python -m stock_data.cli sync-szse-master
```

包括当前 A 股列表、退市证券、股票简称变更。启动时自动调用尚未应用的 migration；重复执行主数据同步会 upsert。

先选 3 只股票验证历史日线：

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 --end 2025-08-31 \
  --codes 000001.SZ 000004.SZ 300001.SZ
```

全深市按批回填（**保持相同日期范围**，重复执行该命令可跳过已成功的股票）：

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 --end 2025-08-31 \
  --batch-size 50 --delay 10 --retries 1
```

`--batch-size` 默认 50，控制每次最多处理多少只**待完成**股票；`--delay` 控制股票间的等待秒数；`--retries` 控制单只股票失败后的额外重试次数。上述 10 秒是近期连接异常后的保守排查设置，**不是 BaoStock 官方限流阈值**。

断点续跑只跳过**股票 + 实际查询日期区间完全匹配**、且 `ingestion_run.status=SUCCESS` 的任务。修改 `--end` 后会按新区间重新获取。必要时对指定股票加 `--force` 忽略检查点；正常续跑请勿使用。零行结果也可能被标记为成功，不能将该状态视为完整性校验。

首次登录及断线重连最多尝试 4 次（等待 2、4、8 秒）；如服务端仍不可用，命令会退出，稍后重跑同一日期窗口即可；已完成股票和数据不会被清空。当前不支持多个进程同时回填同一窗口，也没有自动冷却调度器。

导入**指定日期**的深交所官方日快照：

```bash
python -m stock_data.cli sync-szse-daily --date 2025-09-01
```

官方快照接口可能对部分历史日期返回空结果；当天无数据并不等于休市。请核实日期和原始文件，而不是自动将零行标记为历史行情完整。

## 只读 API

```bash
python -m uvicorn stock_data.api:app --host 127.0.0.1 --port 8000
```

交互文档：http://127.0.0.1:8000/docs

```bash
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/api/instruments?q=平安&limit=10'
curl 'http://127.0.0.1:8000/api/instruments/000001'
curl 'http://127.0.0.1:8000/api/instruments/000001/daily?start=2025-08-01&end=2025-09-01&limit=100'
curl 'http://127.0.0.1:8000/api/market/overview?limit=30'
```

日线默认获取查询窗口中最近 250 条、最多 5000 条，返回的 `bars` 按日期升序；`has_more=true` 时可用 `next_end` 查询更早记录。市场概览的 `as_of` 是**数据库已入库的最新日期**，不是实时行情。API 尚无鉴权，仅供本机开发。

## 测试

```bash
python -m compileall -q stock_data tests
python -m unittest discover -s tests -v
```

数据质量目前仅具备基本的早期行情缺口记录；交易日历对齐、来源价格差异和日快照发布门槛尚未实现。
