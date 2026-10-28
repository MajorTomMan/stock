# Ingestion · Python 沪深 A 股数据采集

本模块负责 SZSE/SSE 主数据、官方日行情、BaoStock 未复权历史回填、PostgreSQL 市场数据与质量检查。HTTP 路由和只读查询已移至 `backend/python/`。**不包含**实时行情、交易或回测功能。

## 项目职责

源码物理存放在 `src/`；安装后导入包和 CLI 入口仍使用 `stock_data`，例如 `python -m stock_data.cli ...`。

| 路径 | 作用 |
| --- | --- |
| `src/providers/` | 对接 BaoStock 与深交所，转换为统一模型 |
| `src/ingestion.py` | 主数据同步、日快照、按股票分批回填 |
| `src/database.py` | 数据存取、采集执行记录、数据质量问题 |
| `src/migrations.py` | 数据表结构版本；由 CLI 自动执行 |
| `backend/python/market_api/` | 独立的 FastAPI 路由和只读查询（不在本模块） |
| `tests/` | 不依赖数据库或网络的单元测试 |
| `data/raw/szse/` | 下载的原始 XLSX（本机生成，已被 Git 忽略） |

`market_daily_observation` 保存各来源原始规范化事实；`market_daily` 选择对外使用的日线。SZSE/SSE 官方来源优先级均为 10，BaoStock 为 50，同一天的 BaoStock 记录不会覆盖已选中的交易所官方记录。价格保留未复权形式；成交量为**股**，成交额为**元**；停牌记录中的 NULL 与 0 保持区别。


股票基本资料采用历史化扩展表，不继续膨胀 `instrument`：

- `share_capital_history`：按生效日期保存总股本、流通股本、自由流通股本，可用于后续市值与换手率计算。
- `instrument_classification`：按分类体系、层级与有效期保存行业/分类历史，可同时容纳交易所、证监会、申万等不同体系。
- 两张表都保留 `source`、可选 `raw_artifact_id` 与 `extra JSONB`，便于追踪来源和容纳源特有字段。
- 当前 `instrument.industry` 继续作为轻量当前展示字段；历史与多体系分类以 `instrument_classification` 为准。
- v2 migration 只新增表，不修改现有 `instrument`、日线、采集记录或已入库数据。当前仅建立结构和数据库写入接口，具体股本/分类数据源将在后续接入。

## 启动（已有数据库无需删除或重新初始化）

在 `ingestion/` 目录运行：

```bash
docker compose up -d
python -m pip install -e .
python -m stock_data.cli migrate
```

默认 PostgreSQL 连接 URL 为 `postgresql://major:majortom@127.0.0.1:10007/stock`。可通过 `DATABASE_URL` 覆盖；`RAW_DATA_DIR` 默认为 `./data/raw`，`HTTP_TIMEOUT_SECONDS` 默认为 40。参考 `.env.example`；CLI 不会自动读取该文件，需要使用环境变量或自行加载。

**重要：**现有 compose 的宿主机端口映射是 `10007:5432`，可能监听所有网络接口。API 示例默认仅监听本机；如需在不受信任的网络环境使用数据库，应单独限制数据库端口访问。Compose 已通过 `name: backend` 复用原项目名与命名卷；旧原始文件如仍在 `backend/data/`，请按 [架构说明](../docs/ARCHITECTURE.md#本地数据保护) 迁移。不要执行 `docker compose down -v`、`docker volume prune` 或 `git clean -fdx`。

## Prefect 3 工作流（推荐入口）

现在使用 Prefect 3 作为 **采集任务编排层**，不取代现有数据源、PostgreSQL、`ingestion_run` 或逐股 checkpoint。上述传统 `stock_data.cli` 命令仍可使用。

首次安装/更新（在 `ingestion/` 目录）：

```bash
python -m pip install -e .
```

执行 Flow：

```bash
# 同步两市证券主数据
python -m stock_data.workflow_cli master

# 同步指定 SZSE 日期 + SSE 最新市场快照，先同步主数据
python -m stock_data.workflow_cli daily --date 2026-10-27

# 已有主数据时可跳过 master 步骤
python -m stock_data.workflow_cli daily --date 2026-10-27 --skip-master

# 历史回填：每次最多 50 只股票，已有成功 checkpoint 会跳过
python -m stock_data.workflow_cli history --exchange SSE \
  --start 1990-12-19 --end 2025-08-31 --batch-size 50 --delay 10 --retries 1

# 深市日期范围：每次最多 30 个尚未处理的工作日
python -m stock_data.workflow_cli szse-range \
  --start 2026-10-01 --end 2026-10-27 --batch-size 30
```

`master` / `daily` 的各交易所步骤是独立 Prefect Task，任务暂时串行执行；一个市场失败仍继续尝试另一个，最终 Flow 以失败结束。网络型 master/daily Task 最多额外重试一次，且写入采用现有 upsert 语义。BaoStock 自带的逐股票重试机制保持不变，**不自动重试整批**；出现部分失败时 Prefect Task 会失败，但已成功股票的数据库 checkpoint 保留。SZSE 日期范围部分失败同理。请求到 0 行不代表已证实休市。

这只是本地 Flow 集成，**不是已经启用的定时任务**。直接运行即可看到终端状态日志；若需要持久化查看运行历史和使用 Web UI，可在另一个终端启动本地服务：

```bash
prefect server start
```

然后在运行 Flow 的终端设置：

```bash
export PREFECT_API_URL=http://127.0.0.1:4200/api
```

打开 http://127.0.0.1:4200 。不需要 Cloudflare、不需要 Prefect Cloud 账号，也不会自动启动额外常驻服务。将来明确部署平台后再设置 Prefect Deployment / Worker / 计划调度。

> Prefect 的 Task 状态是编排层观测；历史是否回填完成仍以 PostgreSQL `ingestion_run` + 实际行情数据为准。并发运行同一个日期窗口或 BaoStock 账号目前未做分布式互斥，**不要同时执行相同的回填 Flow**。

## 采集命令

首次使用时同步深交所主数据：

```bash
python -m stock_data.cli sync-szse-master
```

包括当前 A 股列表、退市证券、股票简称变更。启动时自动调用尚未应用的 migration；重复执行主数据同步会 upsert。

同步上交所主板 A 股、科创板以及已退市证券：

```bash
python -m stock_data.cli sync-sse-master
```

沪市主数据来自上交所股票列表查询接口，主板与科创板都会写入现有 `instrument` 表，分别标记为 `MAIN` / `STAR`；无需新增数据库表。


先选 3 只股票验证历史日线：

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 --end 2025-08-31 \
  --codes 000001.SZ 000004.SZ 300001.SZ
```

深市按批回填（`--exchange SZSE` 是默认值，**保持相同日期范围**即可断点续跑）：

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 --end 2025-08-31 \
  --batch-size 50 --delay 10 --retries 1
```

沪市使用同一个回填命令，只需切换交易所：

```bash
python -m stock_data.cli bootstrap-baostock \
  --exchange SSE \
  --start 1990-12-19 --end 2025-08-31 \
  --batch-size 50 --delay 10 --retries 1
```

BaoStock 会按交易所映射为 `sz.<code>` 或 `sh.<code>`。新的断点记录会同时保存 exchange；历史版本已经完成但没有 exchange 字段的断点继续按 SZSE 识别，不会因为本次改造重新跑一遍深市。


`--batch-size` 默认 50，控制每次最多处理多少只**待完成**股票；`--delay` 控制股票间的等待秒数；`--retries` 控制单只股票失败后的额外重试次数。上述 10 秒是近期连接异常后的保守排查设置，**不是 BaoStock 官方限流阈值**。

断点续跑只跳过**股票 + 实际查询日期区间完全匹配**、且 `ingestion_run.status=SUCCESS` 的任务。修改 `--end` 后会按新区间重新获取。必要时对指定股票加 `--force` 忽略检查点；正常续跑请勿使用。零行结果也可能被标记为成功，不能将该状态视为完整性校验。

首次登录及断线重连最多尝试 4 次（等待 2、4、8 秒）；如服务端仍不可用，命令会退出，稍后重跑同一日期窗口即可；已完成股票和数据不会被清空。当前不支持多个进程同时回填同一窗口，也没有自动冷却调度器。

导入**指定日期**的深交所官方日快照：

```bash
python -m stock_data.cli sync-szse-daily --date 2025-09-01
```

官方快照接口可能对部分历史日期返回空结果；当天无数据并不等于休市。请核实日期和原始文件，而不是自动将零行标记为历史行情完整。

导入上交所**最新交易时段/交易日**的官方市场快照：

```bash
python -m stock_data.cli sync-sse-daily
```

上交所公开行情接口返回的是当前最新市场快照，因此该命令故意不提供 `--date`：它会读取响应中的实际市场日期后入库。历史缺口继续由 BaoStock 回填。重复运行同一交易日会按现有 observation/canonical upsert 逻辑更新，不会制造重复日线。


## 深市按日期范围增量补近期行情

已有 `sync-szse-daily` 只抓一天。以下命令会按日期逐天导入深交所官方快照，每次最多处理 30 个**尚未处理的工作日**：

```bash
python -m stock_data.cli sync-szse-range \
  --start 2025-09-02 --end 2026-09-23 --batch-size 30 --delay 1
```

日期仅为示例；`--end` 请填要补到的已经结束的交易日。重复运行完全相同的命令，会依据现有 `ingestion_run` 成功记录跳过已处理日期并继续下一批；周末自动跳过，法定节假日由于尚无可靠交易日历仍会向来源请求。

单日失败会记录在 `failed_dates`，其他日期仍会继续；命令最终以非零退出码结束，但此前成功入库的数据不会回滚。空结果列在 `empty_dates`，只表示该日没有获得可入库记录，**不能据此判定休市或历史覆盖完整**。默认会跳过已经请求过的空日期，避免续跑反复卡住；如需重新检查它们可加 `--retry-empty`，需要重抓整个窗口则加 `--force`。

`--batch-size` 限制的是日期数量，不是股票数量。该命令只适用于 SZSE，因为当前 SSE 官方公开行情是最新市场快照，历史缺口继续由 BaoStock 回填。

## Parquet 冷数据验证

先不要删除 PostgreSQL 中的任何行情。可以把某一年的 canonical 日线导出成 Zstandard 压缩 Parquet，观察真实体积：

```bash
python -m stock_data.cli export-parquet --exchange SZSE --year 2025
python -m stock_data.cli export-parquet --exchange SSE --year 2025
```

默认分别输出到 `data/archive/market_daily/szse/<year>.parquet` 和 `data/archive/market_daily/sse/<year>.parquet`，并打印行数、Parquet 大小、未压缩 Arrow 大小、压缩倍率和平均每行字节数。导出使用服务端游标分批读取，不会一次把整年数据加载进内存。

当前只导出 canonical `market_daily`，不包含多来源 `market_daily_observation`、PostgreSQL 索引或原始交易所文件。这是冷热分层的可行性验证，不会修改数据库，也不会自动上传 R2。

## 只读 API

FastAPI 路由与只读 SQL 已迁移至 [backend/python/](../backend/python/)，本模块不再运行 HTTP 服务。接口保持原样，启动与请求说明详见对应 README。

## 测试

```bash
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

## 轻量数据检查

直接读取已经入库的日线与来源记录，不新增数据库表、审核状态或外部数据请求：

```bash
python -m stock_data.cli audit-daily --date 2025-09-01
# 可选的只读 HTTP 质检入口见 backend/python/README.md
```

检查现有 OHLC 价格关系、负成交量/金额、SZSE 与 BaoStock 收盘价差异，以及官方最近一次成功导入的条数是否与数据库现存官方行数相同。最多显示前 100 条问题。未填充权威交易日历，所以“NO_DATA”只表示数据库没数据，不能据此判断是否休市或真实缺口；历史完整性检查留待日后真正需要时做。
