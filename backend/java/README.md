# Java Backend · 模拟交易服务（M2）

本目录用于后续 Spring Boot 交易服务，目前仅保留架构边界，**还没有 Java 工程或运行服务**。

计划负责账户、订单、模拟撮合、成交、持仓、资金流水、交易规则和事务一致性。

- 不采集 SSE/SZSE/BaoStock 数据，不运行 pandas/Parquet 任务。
- 只读取由 Python 采集模块维护的 canonical 市场行情。
- Java 独立拥有未来的交易业务数据，不能与 Python 同时写交易表。
- 人工订单和策略订单最终经过同一套模拟撮合逻辑。
- M2 正式开始时再选择 JDK/构建工具并建立 Spring Boot 工程，当前避免空框架。

见 [架构文档](../../docs/ARCHITECTURE.md) 和 [路线图](../../docs/ROADMAP.md)。
