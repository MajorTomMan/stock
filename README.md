# Stock · A 股数据与模拟交易研究平台

长期目标：通过真实 A 股数据建立研究、回测和模拟交易网站。**当前是 M1：行情数据平台**；还没有模拟交易、实盘交易或实时行情。

## 代码结构

```text
stock/
├── ingestion/               # Python：数据源采集、清洗、市场数据库、归档
│   ├── src/                  # 源码物理目录；安装后包名仍为 stock_data
│   ├── tests/
│   ├── pyproject.toml
│   └── docker-compose.yml   # 本地开发 PostgreSQL，不是云部署层
├── backend/
│   ├── python/              # FastAPI：现有只读行情 API
│   └── java/                # Spring Boot：未来 M2 模拟交易模块，尚未实现
├── frontend/                # Vue 3 + Vite
└── docs/                    # 架构约定与长期路线
```

采集源码物理存放在 `ingestion/src/`；安装后导入包和 CLI 入口仍使用 `stock_data`，例如 `python -m stock_data.cli ...`。

仓库不再包含 Cloudflare Containers/Workers 及部署配置。Java 当前是预留模块，并没有启动服务。

## 本地运行

仓库根目录执行：

```bash
cd ingestion
docker compose up -d
python -m pip install -e .
python -m stock_data.cli migrate
cd ..
```

运行 FastAPI：

```bash
python -m pip install -r backend/python/requirements.txt
python -m uvicorn market_api.app:app --app-dir backend/python --host 127.0.0.1 --port 8000
```

另开终端运行 Vue：

```bash
cd frontend
npm install
npm run dev
```

网站：http://127.0.0.1:5173；API 文档：http://127.0.0.1:8000/docs。

采集与回填继续在 `ingestion/` 目录运行 `python -m stock_data.cli ...`。

## 保护现有数据

- Compose 文件已固定 `name: backend`，保留原有项目名及 `backend_postgres18_data` 命名卷，避免重构目录后误建空数据卷。
- 原先被 Git 忽略的 `backend/data/` 不会随源码自动移动；安全迁移方法见 [架构文档](docs/ARCHITECTURE.md#本地数据保护)。
- **不要**执行 `docker compose down -v`、`docker volume prune`、`git clean -fdx`。

## 文档

- [架构分层与边界](docs/ARCHITECTURE.md)
- [长期规划 M1-M4](docs/ROADMAP.md)
- [采集和历史回填](ingestion/README.md)
- [Python API](backend/python/README.md)
- [Java 交易服务](backend/java/README.md)
- [Vue 前端](frontend/README.md)
