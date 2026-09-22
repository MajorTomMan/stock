# Market Data Backend V1

第一阶段只做已经验证过的数据链路：

- **SZSE**：A 股主数据、退市信息、简称变更、最近历史/每日官方快照。
- **BaoStock**：深市长期未复权日线冷启动。
- **PostgreSQL**：保存来源观察值与 canonical 日线。

## 数据选择规则

`market_daily_observation` 保留每个来源的数据；`market_daily` 是当前 canonical 结果。

来源优先级：

- `SZSE = 10`
- `BAOSTOCK = 50`

数字越小优先级越高。因此同一股票同一日期同时存在 SZSE 和 BaoStock 时，`market_daily` 使用 SZSE，但 BaoStock 原记录仍保留在 observation 表中。

## 表

- `instrument`：证券主数据。
- `instrument_name_history`：简称变更历史。
- `trade_calendar`：交易日历预留表。
- `market_daily_observation`：各数据源规范化后的日线事实。
- `market_daily`：按来源优先级选择后的 canonical 日线。
- `ingestion_run`：每次采集执行记录。
- `raw_artifact`：SZSE 原始 XLSX 路径、SHA-256、大小。
- `data_quality_issue`：数据质量问题，例如 `EARLY_HISTORY_GAP`。

成交量统一为 **股**，成交额统一为 **人民币元**。停牌情况下 `volume_shares` / `turnover_cny` 允许为 `NULL`，不强制改成 0。

## 启动 PostgreSQL

```bash
cd backend
docker compose up -d
```

PostgreSQL 对宿主机暴露：

```text
127.0.0.1:10007
```

## 安装 Python 依赖

```bash
cd backend
python -m pip install -r requirements.txt
```

可选环境变量：

```bash
export DATABASE_URL='postgresql://major:majortom@127.0.0.1:10007/stock'
export RAW_DATA_DIR='./data/raw'
```

## 初始化数据库

```bash
python -m stock_data.cli migrate
```

## 1. 同步 SZSE 主数据

```bash
python -m stock_data.cli sync-szse-master
```

会获取并保存：

- `1110/tab1`：A 股列表
- `1793_ssgs/tab2`：终止上市
- `SSGSGMXX/tab2`：简称变更

原始 XLSX 保存在 `data/raw/szse/`。

## 2. 先小规模验证 BaoStock 冷启动

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 \
  --end 2025-08-31 \
  --codes 000001.SZ 000004.SZ 300001.SZ
```

或者只跑前 10 个证券：

```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 \
  --end 2025-08-31 \
  --limit 10
```

确认无误后再去掉 `--codes/--limit` 做全量冷启动。

冷启动是幂等的，可以重跑。若首条行情比官方 `list_date` 晚超过 7 天，会写入：

```text
EARLY_HISTORY_GAP
```

例如我们实测到的早期退市老股缺口会被显式记录，而不是静默忽略。

## 3. 每日 SZSE 官方快照

```bash
python -m stock_data.cli sync-szse-daily --date 2026-09-11
```

`1815_stock_snapshot` 返回的范围包含非 A 股证券，所以写库前会与 `instrument` 主数据交集，只接收已识别的深市 A 股。

## 推荐首次执行顺序

```bash
cd backend
docker compose up -d
python -m pip install -r requirements.txt
python -m stock_data.cli migrate
python -m stock_data.cli sync-szse-master
python -m stock_data.cli bootstrap-baostock --start 1991-01-01 --end 2025-08-31 --codes 000001.SZ 000004.SZ 300001.SZ
python -m stock_data.cli sync-szse-daily --date 2025-09-01
```

最后一条使用我们已经实测确认 SZSE 可返回的日期，方便检查 SZSE 是否正确覆盖 BaoStock canonical 数据。


## 4. 全深市历史回填：分批、断点续跑

建议使用相同的 `--start` 和 `--end` 重复执行。每次最多处理 50 只尚未完成的股票：
 
```bash
python -m stock_data.cli bootstrap-baostock \
  --start 1991-01-01 --end 2025-08-31 --batch-size 50
```

命令结束时打印 `already_completed`、`attempted`、`failed_instruments`、`remaining_pending`。重复运行相同命令时，只跳过具有 **相同实际查询日期区间** 且成功结束的股票；失败的会再次尝试。用户指定 `--codes` 时只处理这些代码，`--batch-size` 在跳过已完成股票后生效。

```bash
# 调试：一次只处理 3 只，单只失败额外重试 3 次
python -m stock_data.cli bootstrap-baostock --start 1991-01-01 --end 2025-08-31 --batch-size 3 --retries 3

# 重新抓取已完成的日期区间（可覆盖同源 observation；不改变来源优先级）
python -m stock_data.cli bootstrap-baostock --start 1991-01-01 --end 2025-08-31 --codes 000001.SZ --force
```

`--delay` 控制股票之间的等待秒数（默认 0.3）。不要在两台机器上对同一日期窗口同时启动该批量任务；V1 没有分布式任务锁。进程被强制结束时，最后一个 `RUNNING` 任务可能留在数据库里，下次运行仍会重试该股票。只有 `SUCCESS` 才作为跳过依据，已有行情不会因为重试被清空。

**注意：**只按完全相同的实际日期区间跳过。修改 `--end` 时会重新获取该股票的新区间；V1 不做重叠区间差集规划。对停牌、非交易日、或尚未有历史数据的股票，零行响应也会记录 `SUCCESS`，不能把它等同于验证该股票每个交易日的数据完备。

## 5. 查询 API（只读 PostgreSQL）

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn stock_data.api:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000/docs 交互调试，或在 Bash 中运行：

```bash
curl 'http://127.0.0.1:8000/health'
curl 'http://127.0.0.1:8000/api/instruments?q=平安&limit=10'
curl 'http://127.0.0.1:8000/api/instruments/000001'
curl 'http://127.0.0.1:8000/api/instruments/000001/daily?start=2025-08-01&end=2025-09-01&limit=100'
curl 'http://127.0.0.1:8000/api/market/overview?limit=30'
```

日线接口默认取所选时间窗口 **最近 250 条**（最大 5000），响应中的 `bars` 按日期升序，便于直接画 K 线。若 `has_more=true`，把 `next_end` 传入下一次请求的 `end` 获取更早的数据。返回 `trade_date`、未复权 OHLC、成交量（股）、成交额（元）、`selected_source` 等字段。

市场概览里的 `as_of` 是**数据库中最新交易日期**，不能当作实时行情。此 API 没有鉴权，只绑定 `127.0.0.1` 本地调试；对外部署前应加鉴权、限流和市场数据展示许可检查。 
