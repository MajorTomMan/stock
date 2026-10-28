# Backend · 后端业务层

本目录只包含后端服务，不再承载采集任务或数据库初始化 CLI。

| 模块 | 技术 | 职责 | 当前状态 |
| --- | --- | --- | --- |
| [python/](python/) | FastAPI | 只读 canonical 市场行情 API、市场查询 | 已实现 |
| [java/](java/) | Spring Boot | 未来 M2 账户、订单、模拟成交、持仓、资金流水和事务 | 仅预留边界 |

Python 采集、行情写入、数据质量检查、Parquet 都在 [ingestion/](../ingestion/)。

```text
市场源 → ingestion/ (Python) → PostgreSQL market 表
                                     │
                                 只读│
                               backend/python/ → 前端
                                     │
                               backend/java/ (M2)
                               只读行情、独立写交易表
```

Java 不替代 Python 采集；M1 阶段依旧只有 FastAPI 运行。

详见 [Python API 启动说明](python/README.md) 和 [架构约定](../docs/ARCHITECTURE.md)。
