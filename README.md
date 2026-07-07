# AI Personal Trading Terminal L4

v0.1：交易计划 + 仓位计算 + 风控 + 决策门。

## 架构

Python monorepo（uv workspace），5 个独立 packages（shared / position-sizing / risk-engine / decision-gate / config-versioning）+ FastAPI 应用 + Next.js 前端。所有核心计算逻辑为纯函数，无 IO，可独立测试。

## 技术栈

- Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 async + Alembic + PostgreSQL 16
- Next.js 14 + TypeScript + Tailwind + TanStack Query + Zustand + react-hook-form + zod
- uv workspace + pnpm workspace
- pytest

## 项目结构

```
.
├── docker-compose.yml              # PostgreSQL 16
├── pyproject.toml                  # uv workspace 根
├── pnpm-workspace.yaml             # pnpm workspace 根
├── uv.toml                         # 清华 PyPI 镜像
├── packages/
│   ├── shared/                     # 枚举 + 基础 schema
│   ├── position-sizing/            # 仓位计算（纯函数）
│   ├── risk-engine/                # 风控引擎（纯函数）
│   ├── decision-gate/              # 决策门（纯函数）
│   └── config-versioning/          # 配置版本（内存实现）
└── apps/
    ├── api/                        # FastAPI 后端
    │   ├── src/app/                # 应用代码
    │   ├── migrations/             # Alembic 迁移
    │   └── tests/                  # pytest 测试
    └── web/                        # Next.js 前端
        ├── app/                    # 路由（plans/risk/settings）
        ├── components/             # 布局 + 计划 + 风控 + 设置组件
        └── lib/                    # API 客户端 + 类型
```

## 开发环境启动

```bash
# 1. 启动 PostgreSQL
docker compose up -d postgres

# 2. 同步 Python 依赖（清华镜像已配置）
uv sync --all-packages

# 3. 创建测试数据库
docker exec crypto_postgres psql -U crypto -c "CREATE DATABASE crypto_terminal_test;"

# 4. 运行数据库迁移
cd apps/api
uv run alembic upgrade head
cd ../..

# 5. 启动后端
cd apps/api
uv run uvicorn src.app.main:app --reload --port 8000

# 6. 启动前端（新终端）
cd apps/web
pnpm install --no-frozen-lockfile
pnpm dev
```

打开 http://localhost:3000 访问前端，后端 API 在 http://localhost:8000。

## 测试

```bash
# 运行所有 Python 测试
uv run pytest -v

# 仅前端 API 集成测试
cd apps/api
uv run pytest tests/ -v

# 仅 packages 单元测试
uv run pytest packages/ -v
```

## v0.1 范围（实现 ✅）

### 核心功能

- [x] 交易计划 CRUD（创建 / 列表 / 详情）
- [x] 仓位计算（risk_amount / notional / rounded_size / required_margin / RR）
- [x] 13 条硬阻断规则（无止损 / 超杠杆 / 超 RR / 止损太近 / 日亏损限制 / 连亏限制 / 冷却期 / Kill Switch / DB 不健康 / 等级阻断 / 等等）
- [x] 等级映射（A→ALLOW / B→REDUCE_RISK / C→BLOCK / BLOCKED→BLOCK）
- [x] Decision Gate 5 状态（ALLOW_CONFIRM / REDUCE_RISK / WAIT / BLOCK / EXPIRED）
- [x] 配置版本管理（创建 / 列出 / 激活）
- [x] 系统 API（status / kill-switch / execution-mode）
- [x] 风控结果落库（position_sizing_results / risk_checks / decision_gate_results）

### 前端页面

- [x] Trade Plans（创建 / 列表 / 详情 + 检查）
- [x] Risk Center（配置展示 / Kill Switch / 版本管理）
- [x] Settings（账户权益 / 配置展示）

### 数据

- [x] 8 张表：trade_plans / position_sizing_results / risk_checks / decision_gate_results / config_versions / system_events / user_settings / account_risk_states
- [x] 部分唯一索引：每配置类型只能有一个激活版本
- [x] Seed 数据：risk-v1 / execution-v1 / opportunity_grade-v1 / symbol_rules-v1（BTC/ETH/SOL）

## v0.2 范围（待实现）

- 行情数据接入（K 线、订单簿）
- Bitget 交易所适配器
- 真实订单提交
- AI 评估（机会评分）
- 用户确认流（UI 弹窗）
- 交易日志（journal）

## 设计文档

- [v0.1 设计稿](docs/superpowers/specs/2026-07-07-crypto-trading-terminal-v0.1-design.md)
- [v0.1 实现计划](docs/superpowers/plans/2026-07-07-crypto-trading-terminal-v0.1.md)
- [L4 文档包](ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/)

## 关键约定

- 所有 Decimal 用 `Decimal`，避免浮点误差
- 响应格式：`{success, data, error, request_id}` 信封
- 错误码：`DUPLICATE_LABEL` / `INVALID_CONFIG_TYPE` / `CONFIG_NOT_FOUND` / `PLAN_NOT_FOUND` / `INVALID_INPUT` 等
- 提交规范：每个 task 独立 commit，feat(<scope>) 前缀
- uv 镜像：清华源（uv.toml 中配置）
