# Stock 项目长期规划

> 状态：长期方向已确定，具体实现按里程碑推进。  
> 核心目标：基于真实 A 股市场数据，构建一个可持续运行的个人量化研究与模拟交易平台。  
> 边界：只做模拟交易与研究，不连接真实券商，不执行真实资金交易。

## 1. 产品目标

项目最终不只是“股票行情网站”，而是一条完整的研究与模拟交易链路：

```text
市场数据
   ↓
数据清洗 / 校验 / 历史化
   ↓
市场状态
   ↓
人工决策 / 策略信号
   ↓
订单
   ↓
模拟撮合
   ↓
成交
   ↓
资金 / 持仓
   ↓
组合收益
   ↓
分析 / 回测 / 复盘
```

最终希望同时支持：

- 股票目录、搜索、K 线、成交量、估值和公司基础资料。
- 历史时间机器：在过去某个交易日开始模拟交易，只能看到当时已知的数据。
- 虚拟账户：现金、订单、成交、持仓、盈亏、资金流水。
- A 股交易规则模拟：整手、T+1、停牌、涨跌停、ST、手续费、印花税等。
- 投资组合分析：收益、回撤、波动、胜率、成本、行业暴露、基准比较。
- 策略回测和模拟盘：策略与人工交易共用同一套市场数据和交易引擎。

## 2. 核心原则

### 2.1 一份市场事实，多种上层用途

网站、回测、策略和模拟交易必须使用同一份 canonical 市场数据，禁止各自维护一套行情。

```text
                    Market Data
                        │
             ┌──────────┼──────────┐
             ▼          ▼          ▼
           网站        回测        策略
             │          │          │
             └────── Order ────────┘
                        │
                 Execution Engine
                        │
                 Portfolio Engine
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
          模拟账户               绩效分析
```

### 2.2 来源事实与 canonical 分离

继续保留：

- `market_daily_observation`：不同来源的规范化事实。
- `market_daily`：最终对外使用的 canonical 日线。

来源优先级原则：

1. SSE / SZSE 官方数据：权威来源，优先级最高。
2. 长期 API 数据源：承担稳定的每日数据和指标补充。
3. BaoStock：历史回填、补洞和兜底。

不要因为接入新数据源而绕过 observation → canonical 体系。

### 2.3 历史信息必须历史化

会随时间变化的字段不得只保存“当前值”。

已经或计划历史化的内容：

- 股票简称：`instrument_name_history`
- 股本：`share_capital_history`
- 行业/分类：`instrument_classification`
- 公司行为：计划 `corporate_action`
- 复权因子：计划 `adjust_factor`
- 每日估值/市值指标：计划 `market_daily_metric`

`instrument` 只承担证券身份和当前展示字段，不继续无限增加历史属性。

### 2.4 模拟交易宁可简单，也不能虚假

第一版撮合可以只支持日线级别，但必须明确规则。例如：

- 无行情/停牌不可成交。
- 限价单只有在当日价格区间允许时才可能成交。
- 买入遵守 100 股整数手。
- A 股持仓遵守 T+1。
- 手续费和税费写入资金流水。
- 所有成交必须来自真实市场价格范围，而不是任意填写成交价。

以后有分钟级数据再升级撮合精度。

## 3. 技术架构

### 3.1 前端

长期保持：

```text
Vue 3
Vite
```

负责：

- 股票浏览与研究界面。
- K 线和指标展示。
- 模拟交易账户与订单界面。
- 组合分析和回测结果展示。

### 3.2 Python：市场数据与量化

Python 长期保留，不迁移到 Java。

负责：

- SSE / SZSE / 第三方数据源采集。
- 数据清洗、标准化、质量检查。
- 历史回填。
- pandas / NumPy / PyArrow 数据处理。
- Parquet 导出。
- 指标计算。
- 策略研究。
- 回测。
- 后续策略运行服务。

现有 FastAPI 只读 API 已迁移至 `backend/python/`，Python 数据采集与市场数据包位于 `ingestion/`；未来 Java 交易服务单独位于 `backend/java/`。

计划逐步采用：

```text
SQLAlchemy
Alembic
PostgreSQL
```

原则：

- 业务实体和普通 CRUD 使用 SQLAlchemy ORM。
- 大批量行情写入、PostgreSQL 特有 SQL、窗口查询、批量 UPSERT、归档继续允许 SQLAlchemy Core 或原生 SQL。
- 不为了 ORM 强行重写性能敏感 SQL。
- schema 进入模拟交易阶段前逐步从自维护 `migrations.py` 迁移到 Alembic。

### 3.3 Spring Boot：模拟交易核心

现在不重写 Python 后端。

到 M2 模拟交易阶段再引入 Spring Boot，负责强事务业务：

```text
Account
Portfolio
Order
Trade
Position
CashLedger
PositionLedger
Risk / Trading Rules
```

Spring Boot 的职责重点是：

- 事务边界。
- 订单状态机。
- 资金冻结与释放。
- 成交后资金/持仓一致性。
- 幂等。
- 乐观锁/并发控制。
- 审计。

Python 不负责模拟账户资金一致性；Spring Boot 不负责 pandas/量化研究。

长期可以按 PostgreSQL schema 分离：

```text
market.*
    Python 主写

trading.*
    Spring Boot 主写
```

两边共享证券 ID 和 canonical 市场事实，但禁止多个服务同时拥有同一业务实体的写权限。

## 4. 数据与存储

### 4.1 PostgreSQL：热数据和业务状态

保留：

- `instrument`
- `instrument_name_history`
- `instrument_classification`
- `share_capital_history`
- `trade_calendar`
- `market_daily`
- `market_daily_observation`
- `ingestion_run`
- `raw_artifact`
- `data_quality_issue`

后续增加：

- `market_daily_metric`
- `corporate_action`
- `adjust_factor`
- trading schema 下的账户/订单/成交/持仓/流水。

### 4.2 R2 / Parquet：原始和冷数据

对象存储承担：

```text
raw/
├── szse/
├── sse/
└── third-party/

archive/
└── market_daily/
    ├── szse/
    └── sse/
```

原则：

- 原始文件不依赖短生命周期容器本地磁盘。
- PostgreSQL 仍是近期查询和业务状态主库。
- 历史行情达到一定规模后，再将老数据按年归档到 Parquet。
- 在验证 PostgreSQL 与 Parquet 查询等价、R2 读取链路稳定之前，不删除数据库中的正式数据。

## 5. 数据源策略

### 当前

- SSE 官方：主数据 + 最新官方行情。
- SZSE 官方：主数据 + 可获得的官方日行情。
- BaoStock：未复权历史回填。

### 长期

新增一个稳定、正式 API 化的数据源作为日常主力，优先补齐：

- 日线。
- 股票基础信息。
- 每日估值指标。
- 股本。
- 复权因子。

无论采用哪个第三方源，都必须满足：

- 可长期自动化。
- 明确 API，而不是依赖网页私有接口。
- 能记录 provider/source。
- 可以进入 observation/canonical 体系。
- 不能成为唯一数据源。

## 6. 代码分层与运行边界

当前仓库不维护云部署层，也不提前绑定 Cloudflare、VM 或数据库托管商。仅保留用于本地开发的 PostgreSQL Compose，原数据库及本地原始文件需安全保留。

代码已按三个功能层整理：

- `ingestion/`：Python 采集、清洗、market 数据写入、质量检查、Parquet。
- `backend/python/`：FastAPI 只读行情查询；`backend/java/`：M2 模拟交易的 Spring Boot 业务边界。
- `frontend/`：Vue 网站。

如后续确有上线需求，再按实际运行环境补充部署配置，避免业务代码绑定云厂商。详情见 [分层架构](ARCHITECTURE.md)。

## 7. 路线图

### M1：可靠市场数据平台

目标：

> 不打开开发电脑，市场数据仍能自动更新；任意正常 A 股可以查询可靠的历史和基础资料。

完成标准：

- [x] 沪深证券主数据
- [x] 名称历史
- [x] canonical / observation 分层
- [x] BaoStock 历史回填机制
- [x] SSE/SZSE 官方行情
- [x] ingestion checkpoint
- [x] 股本历史 schema
- [x] 分类历史 schema
- [x] Parquet PoC
- [ ] 全市场历史日线达到可接受覆盖率
- [ ] 可靠交易日历
- [ ] 长期主数据源
- [ ] 股本实际数据
- [ ] 行业分类实际数据
- [ ] 每日估值/市值指标
- [ ] 复权因子
- [ ] 公司行为
- [ ] 自动日更
- [ ] 数据质量监控与缺口检查
- [ ] raw / archive 持久化

M1 完成前，不优先建设复杂交易功能。

### M2：模拟交易 MVP

目标：

> 用户可以拿一笔虚拟资金，根据真实市场数据完成可信的 A 股模拟买卖。

第一版模型：

- Account
- Portfolio
- Order
- Trade
- Position
- CashLedger

第一版规则：

- 虚拟初始资金。
- 买入 / 卖出 / 撤单。
- 100 股整数手。
- T+1。
- 停牌不可成交。
- 涨跌停约束。
- ST 状态规则。
- 手续费、印花税、过户费。
- 已实现 / 未实现盈亏。
- 资产曲线。

M2 开始时引入 Spring Boot 交易服务。

### M3：历史研究与策略平台

目标：

> 同一套数据和执行模型同时服务人工模拟盘和策略研究。

包括：

- 历史时间机器。
- 防止未来数据泄漏。
- 回测框架。
- 策略接口。
- 基准比较。
- 最大回撤、波动率、胜率、盈亏比等绩效统计。
- 选股器。
- 自动产生模拟订单。
- 模拟盘日报。

策略发出的订单必须经过与人工订单相同的交易规则和撮合引擎。

### M4：长期扩展

在 M1-M3 稳定后再考虑：

- 多用户。
- 多组合。
- 策略排行榜。
- 模拟交易比赛。
- 分钟行情。
- 更精细的撮合。
- 港股/ETF/可转债等新资产。

这些需求不提前污染 M1/M2 的模型。

## 8. 当前明确不做

现阶段不做：

- 真实券商连接。
- 实盘自动交易。
- 高频交易。
- Level-2。
- 为了“微服务”而拆微服务。
- 为了 ORM 而 ORM 化所有行情 SQL。
- 为了云厂商而重写核心采集逻辑。
- 在 M1 未稳定前同时开发大量交易功能。
- 无意义地增加基础设施复杂度。

## 9. 功能优先级判断

以后每个新需求先回答：

1. 它是否直接推进 M1、M2 或 M3？
2. 它解决的是实际数据/交易问题，还是只增加架构复杂度？
3. 它是否会造成新的数据源或业务状态重复？
4. 能否保持“一个市场事实、一套交易引擎”？
5. 是否现在必须做？

若一个需求不能明确推进当前里程碑，默认延后。

## 10. 近期执行顺序

当前只推进 M1：

```text
长期主数据源
      ↓
trade_calendar
      ↓
adjust_factor / corporate_action
      ↓
share capital 实际数据
      ↓
daily metrics / classification
      ↓
自动化采集
      ↓
数据质量检查
      ↓
全市场历史覆盖验证
      ↓
M1 完成
      ↓
开始 M2
```

在 M1 完成前，Spring Boot 只作为已经确定的 M2 技术方向，不提前启动 Java 服务。
