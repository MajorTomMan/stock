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
