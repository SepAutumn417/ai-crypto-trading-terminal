# AI Personal Trading Terminal L4

![CI](https://img.shields.io/badge/CI-GitHub%20Actions-blue?logo=github)

风险优先的加密货币个人交易研究终端。Python monorepo + FastAPI + Next.js 前端。

> **⚠️ 重要声明**：当前系统是"风险优先交易研究终端"，尚未达到可安全托付真实资金的交易执行系统标准。
> "指标评分"模块（原 AI Evaluator）是基于 RSI/MACD/布林带/均线/成交量的固定规则加权评分，非 AI 模型预测，
> 评分不构成交易建议，也不保证具有统计意义上的交易优势。

## 架构

Python monorepo（uv workspace），9 个独立 packages + FastAPI 应用 + Next.js 15 前端。
所有核心计算逻辑为纯函数，无 IO，可独立测试。

## 技术栈

- Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 async + Alembic + PostgreSQL 16
- Next.js 15 + TypeScript + Tailwind + TanStack Query + Zustand + react-hook-form + zod
- uv workspace + pnpm workspace
- pytest（`--import-mode=importlib`）

## 项目结构

```
.
├── docker-compose.yml              # PostgreSQL 16
├── pyproject.toml                  # uv workspace 根
├── pnpm-workspace.yaml             # pnpm workspace 根
├── uv.toml                         # 清华 PyPI 镜像
├── packages/
│   ├── shared/                     # 枚举 + 基础 schema + 配置模型
│   ├── position-sizing/            # 仓位计算（含双边手续费/滑点/资金费率）
│   ├── risk-engine/                # 风控引擎（13 条硬阻断规则）
│   ├── decision-gate/              # 决策门（5 状态融合矩阵）
│   ├── config-versioning/          # 配置版本管理
│   ├── exchange-adapter/           # Bitget V2 交易所适配器
│   ├── ai-evaluator/               # 技术指标评分器（固定规则加权，非 AI 模型）
│   ├── market-structure/           # 市场结构识别（Fractal/BOS/CHOCH/支撑压力区）
│   └── auto-plan-engine/           # 自动候选计划生成（7 种 Setup + 6 维评级 + 9 状态机）
└── apps/
    ├── api/                        # FastAPI 后端
    │   ├── src/app/                # 应用代码
    │   ├── migrations/             # Alembic 迁移
    │   └── tests/                  # pytest 测试
    └── web/                        # Next.js 15 前端
        ├── app/                    # 路由（market/radar/ai/plans/journal/risk/settings）
        ├── components/             # 布局 + 计划 + 风控 + 设置 + AI + 行情组件
        └── lib/                    # API 客户端 + 类型
```

## 安全特性（P0 已修复）

- **REAL_TRADING_ENABLED 硬开关**：进程级环境变量，默认 `false`，阻止真实下单
- **REST API 全面认证**：所有高风险端点需 Bearer token（`API_TOKEN` 环境变量）
- **默认监听 127.0.0.1**：API 不暴露到局域网（可通过 `API_HOST` 配置）
- **WebSocket token 认证**：fail-closed 策略，未配置 token 时拒绝连接
- **服务端二次确认**：plan_hash（SHA256）+ 一次性 token + TTL + 口令验证
- **执行前重新检查**：风险配置版本、计划有效期、行情偏离
- **幂等下单**：稳定 client_order_id（仅基于 plan_id），行锁 + EXECUTING 中间态
- **对账恢复**：按 clientOid 查询交易所，UNKNOWN/RECONCILIATION_REQUIRED 状态
- **Kill Switch 联动**：激活时强制关闭 execution mode，拒绝开启；自动触发（孤儿订单/对账失败/风控超限）

## 开发环境启动

```bash
# 1. 启动 PostgreSQL
docker compose up -d postgres

# 2. 同步 Python 依赖
uv sync --all-packages

# 3. 创建测试数据库
docker exec crypto_postgres psql -U crypto -c "CREATE DATABASE crypto_terminal_test;"

# 4. 运行数据库迁移
cd apps/api
uv run alembic upgrade head
cd ../..

# 5. 启动后端（默认仅监听 127.0.0.1）
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
# 运行所有 Python 测试（使用 importlib 模式避免包名冲突）
uv run pytest -v --tb=short

# 仅 API 集成测试
cd apps/api
uv run pytest tests/ -v
cd ../..

# 仅 packages 单元测试
uv run pytest packages/ -v

# 前端 lint + 类型检查 + 构建
cd apps/web
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

## 版本路线

| 版本 | 范围 | 状态 |
|------|------|------|
| v0.1 | 交易计划 + 仓位计算 + 风控 + 决策门 + 配置版本管理 | ✅ 已交付 |
| v0.2 | 行情接入与 K 线图表（Bitget REST K 线、K 线入库、K 线图展示） | ✅ 已交付 |
| v0.3 | 市场结构识别（Swing High/Low、BOS/CHOCH、支撑压力区、无交易区） | ✅ 已交付 |
| v0.4 | 自动候选计划生成（Opportunity Radar、7 种 Setup、6 维评级、9 状态机） | ✅ 已交付 |
| v0.5 | 技术指标评分与解释（结构解释、计划质量分析、风险解释） | ✅ 已交付 |
| v0.6 | 订单预览与 Dry Run（Order Intent、Order Preview、执行日志） | 🚧 进行中 |
| v0.7 | 只读实盘同步（读取账户权益/持仓/订单/成交、持仓监控） | ⏳ |
| v0.8 | 小额 L4 确认执行（启用交易 Key、用户确认后提交限价单、Kill Switch） | ⏳ |
| v1.0 | 完整 L4 个人交易终端（Dashboard、Opportunity Radar、Chart Workspace、Journal、Review） | ⏳ |

## 关键约定

- 所有 Decimal 用 `Decimal`，避免浮点误差
- 响应格式：`{success, data, error, request_id}` 信封
- 错误码：`DUPLICATE_LABEL` / `INVALID_CONFIG_TYPE` / `CONFIG_NOT_FOUND` / `PLAN_NOT_FOUND` / `INVALID_INPUT` / `KILL_SWITCH_ACTIVE` / `NOT_CONFIRMED` / `CONFIRMATION_EXPIRED` 等
- 提交规范：每个 task 独立 commit，feat(<scope>) 前缀
- uv 镜像：清华源（uv.toml 中配置）
- 仓位模型最大损失 = 风险金额 + 双边手续费 + 滑点 + 资金费率

## 设计文档

- [v0.1 设计稿](docs/superpowers/specs/2026-07-07-crypto-trading-terminal-v0.1-design.md)
- [v0.1 实现计划](docs/superpowers/plans/2026-07-07-crypto-trading-terminal-v0.1.md)
- [L4 文档包](ai-personal-trading-terminal-docs/ai-personal-trading-terminal-l4-docs/)
