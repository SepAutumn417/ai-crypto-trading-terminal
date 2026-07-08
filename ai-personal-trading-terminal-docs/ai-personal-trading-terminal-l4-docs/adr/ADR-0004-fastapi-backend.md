# ADR-0004：后端采用 FastAPI

## 状态

Accepted（2026-07-07）

## 背景

系统后端需要处理：行情接入、结构识别算法、风控引擎、AI 评估调用、订单执行、配置版本管理、WebSocket 推送。技术栈选型需平衡以下诉求：

- **AI / 算法生态**：结构识别、AI 评估、未来策略回测深度依赖 Python 的 ML/数据处理生态（pandas、numpy、ta-lib、llm SDK）；
- **异步 IO**：行情 WebSocket、订单 WebSocket、前端 WebSocket 需要高并发异步处理；
- **类型安全**：配置、风控规则、订单参数需要严格的输入校验，避免运行时类型错误导致下单事故；
- **API 文档**：前端需要准确的接口契约，手写文档易过期；
- **单人开发效率**：个人项目，框架学习成本与样板代码量要低。

候选栈：FastAPI（Python）、NestJS（Node）、Go（net/http 或 fiber）、Django（Python）。

## 决策

后端采用 **FastAPI + Pydantic v2 + SQLAlchemy 2.0（async）+ Alembic**。

- `apps/api/`：FastAPI 应用 + Alembic 迁移；
- `packages/`：领域纯逻辑（risk_engine、structure、ai_client 等），框架无关；
- 包管理：uv（Python workspace）；
- 测试：pytest + pytest-asyncio + httpx。

## 后果

**正面**：

- Python ML 生态直接可用，结构识别与 AI 评估无需跨语言调用；
- Pydantic v2 提供编译级校验，ValidationError 结构化输出（见 `ERROR_CODES.md §5`）；
- FastAPI 自动生成 OpenAPI，前端类型可从 schema 生成，契约一致；
- async/await 原生支持，WebSocket 与 REST 共享事件循环；
- 单人开发样板少，依赖注入轻量。

**负面**：

- 单进程 + GIL：CPU 密集的结构识别算法会阻塞事件循环，需用 `run_in_executor` 或独立进程；
- Python 运行时性能弱于 Go/Node（对单用户终端可接受，见 `PRD.md §8.5`）；
- SQLAlchemy 2.0 async 生态相对新，部分工具链支持不完整；
- 部署需 Python 运行时 + 虚拟环境，不如 Go 单二进制方便。

**强制约束**：

- 所有金额、价格、数量计算使用 Python `Decimal`，不使用 `float`（见 spec §3.5）；
- 数据库字段用 `NUMERIC`（见 `DATABASE.md §5`）；
- 风控引擎为纯函数，不依赖 FastAPI 的 Request/Response 对象，保证可独立测试；
- Alembic 迁移与 ORM 模型必须同步（见 `project_memory.md` 工程约定）。

## 备选方案

| 方案 | 拒绝原因 |
|---|---|
| **NestJS（Node）** | 前后端同语言有吸引力，但 ML/结构识别生态弱于 Python，需跨语言调用 Python 算法，增加运维复杂度 |
| **Go（fiber / net/http）** | 性能与部署优秀，但 ML 生态空白，AI/结构算法需另起 Python 服务，双语言运维成本高 |
| **Django** | ORM 与 admin 成熟，但异步支持不如 FastAPI 原生，WebSocket 链路需 Channels 额外引入；样板较重 |
| **Flask + 扩展** | 异步生态不成熟，类型校验需手动集成，API 文档需手写 |

## 关联

- v0.1 spec §3.1：技术栈选型表；
- `DATABASE.md §5`：NUMERIC 精度规范；
- `ERROR_CODES.md §5`：Pydantic ValidationError 详情格式；
- `project_memory.md`：Alembic 与 ORM 同步、lazy engine 等工程约定。
