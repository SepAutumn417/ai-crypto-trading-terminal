# AI Personal Trading Terminal L4 — v0.1 设计文档

## 0. 文档定位

本文档是 v0.1 阶段的实施设计稿，基于 `f:\crypto\ai-personal-trading-terminal-docs\ai-personal-trading-terminal-l4-docs\` 下的 L4 文档包（PRD、SCOPE、SYSTEM_DESIGN、MODULES、DEVELOPMENT、MVP_ACCEPTANCE、FRONTEND_PAGES、RISK_RULES、API、DATABASE、AUTOMATION_DESIGN、EXECUTION_DESIGN、EXECUTION_SAFETY、ORDER_LIFECYCLE、ADR-0001/0002/0003 等）。

v0.1 不重新定义业务规则，只对 L4 文档包做实施层面的裁剪与具化。所有业务约束以原文档为准；本设计稿只声明 v0.1 范围内做什么、怎么组织代码、怎么验收。

---

## 1. v0.1 范围

### 1.1 做什么（对齐 MVP_ACCEPTANCE.md v0.1）

- 手动创建交易计划：输入入场价、止损价、止盈价、杠杆、风险比例、机会等级、账户权益、symbol、direction。
- 自动仓位计算：风险金额、止损距离、名义仓位、所需保证金、预估手续费、盈亏比、预估止损亏损。
- 风控引擎硬检查：完整实现 RISK_RULES.md 中的硬禁止规则、降风险规则、等待规则、机会等级与风险权限映射。
- 决策门：输出 ALLOW_CONFIRM / WAIT / REDUCE_RISK / BLOCK / EXPIRED。v0.1 不接 AI，`aiEvaluation` 入参位保留为 Optional。
- 配置版本管理：风控配置、执行配置、机会等级配置、symbol rules 配置均可版本化、可激活历史版本。
- 账户风险状态追踪：当日亏损 R、连亏次数、冷却期。
- Kill Switch 与 Execution Mode 状态管理。
- 系统事件审计：Kill Switch 切换、配置激活、风控拦截等事件落 system_events。
- 单元测试覆盖核心计算逻辑。

### 1.2 不做什么（推迟到后续版本）

| 推迟项 | 目标版本 |
|---|---|
| 行情接入、K线展示 | v0.2 |
| 市场结构识别 | v0.3 |
| 自动候选计划生成 | v0.4 |
| AI 评估 | v0.5 |
| 订单预览、Dry Run | v0.6 |
| 交易所接入、只读同步 | v0.7 |
| 真实下单 | v0.8 |
| 完整 L4 终端 | v1.0 |

### 1.3 v0.1 与原设计的差异说明

v0.1 不做业务简化，只做数据源差异处理：

1. **账户权益来源**：v0.1 由用户手动输入并存入 `user_settings.account_equity`。这是 v0.1 范围决定（不接交易所），不是简化。v0.7 接入 Bitget 后改为交易所同步。
2. **symbol rules**：v0.1 由用户在 Settings 页面配置（默认填 BTC/ETH/SOL 的常见合约参数）。v0.7 接入 Bitget 后用 `getSymbolRules` 真实规则覆盖。
3. **当日亏损 / 连亏 / 冷却期**：v0.1 完整实现检查逻辑，但**写入路径为只读**——`account_risk_state` 表存在并有 seed 初始值（全 0/false），但 v0.1 没有真实成交，没有任何 API/service 会更新这些字段。v0.8 接入真实成交后由 execution-engine 在平仓时更新。v0.1 期间可通过手动构造 DB 数据测试风控规则 6/7/8。
4. **exchange_connected 降级**：RISK_RULES.md §5 规则 10"WebSocket/交易所状态异常 → BLOCK"，但 v0.1 无交易所接入，`exchange_connected=false` 属正常状态。v0.1 中此项**降级为 warning，不 BLOCK**。v0.7 接入 Bitget 后恢复为 BLOCK。此降级已在 `packages/risk-engine/src/risk_engine/checker.py` 中实现。
5. **DecisionGate 输入简化**：MODULES.md §10 定义 DecisionGate 输入为 `plan / risk result / AI evaluation / system mode / execution enabled / user settings`。v0.1 简化为 `risk_result / execution_enabled / kill_switch / ai_evaluation(None) / plan_expired`，省略了 `plan` 对象本身、`system mode`、`user settings`（v0.1 无 system mode 切换，user_settings 中的 execution_enabled/kill_switch 已直接传入）。v0.5+ 接入 AI 与 system mode 后补齐。

风控引擎、position-sizing、decision-gate 都是生产级完整实现，后续版本只接入数据源，不重写核心逻辑。

---

## 2. 架构

### 2.1 仓库结构

遵循 MODULES.md 的 monorepo 形态，按 v0.1 范围裁剪：

```text
f:\crypto\
  apps\
    web\                  # Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui
    api\                  # FastAPI + SQLAlchemy 2.0 (async) + Alembic
  packages\               # Python 包（uv workspace）
    shared\               # Pydantic schemas、枚举、错误类型
    position-sizing\      # 仓位计算纯逻辑
    risk-engine\          # 硬风控规则纯逻辑
    decision-gate\        # 决策门
    config-versioning\    # 配置版本管理
  docker-compose.yml      # PostgreSQL 16
  pyproject.toml          # uv workspace 根
  package.json            # pnpm workspace 根
  .env.example
  .gitignore
  README.md
```

v0.1 不创建的 packages（v0.2+ 按版本加入）：`market-data`、`market-structure`、`auto-plan-engine`、`ai-evaluation-agent`、`execution-engine`、`exchange-adapters`、`journal`、`review`、`event-log`。

### 2.2 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 前端框架 | Next.js 14 App Router | 文档推荐，生态成熟 |
| 前端语言 | TypeScript | 类型安全 |
| 样式 | Tailwind CSS | 文档推荐 |
| 组件库 | shadcn/ui（Table、Form、Dialog、Badge、Button、Tabs、Switch） | 可定制、无运行时开销 |
| 表单 | react-hook-form + zod | 校验与类型联动 |
| 前端状态 | Zustand | 轻量，v0.1 够用 |
| 数据请求 | TanStack Query | 缓存、乐观更新 |
| 后端框架 | FastAPI + Pydantic v2 | 文档推荐，Python 生态适合后续 AI/结构算法 |
| ORM | SQLAlchemy 2.0 (async) + Alembic | 主流、迁移可控 |
| 数据库 | PostgreSQL 16（Docker） | 文档指定 |
| 缓存 | 暂不引入 Redis | v0.1 无实时数据、无任务队列；v0.2 接入行情时再引入 |
| 测试 | pytest + pytest-asyncio + httpx | Python 标准 |
| 包管理 | uv（Python）+ pnpm（前端） | 速度快、workspace 原生支持 |
| 部署 | 本地开发，docker-compose 只起 PostgreSQL | v0.1 不做生产部署 |

### 2.3 核心调用流（POST /api/trade-plans/{id}/check）

```text
load trade_plan (status=DRAFT)
  ↓
load active configs:
  - risk_config
  - execution_config
  - opportunity_grade_config
  - symbol_rules (for plan.symbol)
  - account_risk_state (dailyLossR / consecutiveLosses / cooldownUntil)
  - user_settings (executionEnabled / killSwitch / accountEquity)
  ↓
position-sizing.calculate(plan, equity, symbolRules, feeRate)
  → PositionSizingResult  (持久化到 position_sizing_results)
  ↓
risk-engine.check(sizingResult, riskConfig, accountState, opportunityGradeConfig)
  → RiskCheckResult  (持久化到 risk_checks)
  ↓
decision-gate.decide(riskResult, executionEnabled, killSwitch, aiEvaluation=None)
  → DecisionGateResult  (持久化到 decision_gate_results)
  ↓
update trade_plan.status:
  - ALLOW_CONFIRM → READY_FOR_CONFIRMATION
  - REDUCE_RISK   → CHECKED（带 warning，用户可调整后重检）
  - WAIT          → CHECKED（带等待原因）
  - BLOCK         → CHECKED（带 blockReasons）
  - EXPIRED       → EXPIRED
  ↓
return { sizing, risk, decision, planStatus }
```

整个 check 在单个 DB 事务内完成，保证 position_sizing_results + risk_checks + decision_gate_results + trade_plan.status 一起落库或一起回滚。

---

## 3. 后端模块设计

### 3.1 packages/shared

公共 schema、枚举、错误类型。所有包共享，无业务逻辑。

**Pydantic 模型**：
- `TradePlanInput`：创建交易计划的入参
- `TradePlan`：持久化后的交易计划
- `PositionSizingResult`：仓位计算结果
- `RiskCheckResult`：风控检查结果
- `DecisionGateResult`：决策门结果
- `RiskConfig` / `ExecutionConfig` / `OpportunityGradeConfig` / `SymbolRules`：配置 schema
- `AccountRiskState`：账户风险状态
- `UserSettings`：用户设置
- `SystemEvent`：系统事件
- `ApiResponse[T]` / `ApiError`：统一响应封装

**枚举**：
- `Direction`：LONG / SHORT
- `MarginMode`：ISOLATED / CROSSED
- `OrderType`：LIMIT / MARKET（v0.1 仅占位，不实际下单）
- `OpportunityGrade`：A / B / C / BLOCKED
- `RiskStatus`：ALLOW / ALLOW_CONFIRM / WARN / REDUCE_RISK / BLOCK
- `DecisionGateStatus`：ALLOW_CONFIRM / WAIT / REDUCE_RISK / BLOCK / EXPIRED
- `PlanStatus`：DRAFT / CHECKED / READY_FOR_CONFIRMATION / EXPIRED / CANCELLED
- `ConfigType`：RISK / EXECUTION / OPPORTUNITY_GRADE / SYMBOL_RULES

**错误类型**：
- `RiskBlockError`：风控拦截时抛出
- `ConfigNotFoundError`：配置不存在时抛出
- `PlanNotFoundError` / `PlanStatusError`：计划查询/状态异常时抛出

### 3.2 packages/position-sizing

纯函数，无 IO。

**入口**：
```python
def calculate(
    equity: Decimal,
    risk_percent: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    take_profit_prices: list[Decimal],
    leverage: Decimal,
    fee_rate: Decimal,
    direction: Direction,
    symbol_rules: SymbolRules,
) -> PositionSizingResult
```

**计算公式**（对齐 RISK_RULES.md §3）：
```text
risk_amount = equity * risk_percent
stop_distance_percent = abs(entry_price - stop_loss_price) / entry_price
notional_value = risk_amount / stop_distance_percent
raw_size = notional_value / entry_price      # 按 entry_price 换算合约数量
rounded_size = round_to_step(raw_size, symbol_rules.size_step)
required_margin = notional_value / leverage
estimated_fee = notional_value * fee_rate
risk_reward_ratio = take_profit_distance / stop_distance   # 取第一个止盈
estimated_loss_at_stop = risk_amount + estimated_fee
```

**精度圆整**：
- `round_to_step(value, step)`：按 step 向下取整（开仓量不能超过计算值）
- 校验 `rounded_size * entry_price >= symbol_rules.min_notional`
- 校验 `rounded_size >= symbol_rules.min_size`
- 若圆整后不满足最小要求，返回 `rounded_size=None` 并带 reason，由 risk-engine 判 BLOCK

### 3.3 packages/risk-engine

纯函数，无 IO。完整实现 RISK_RULES.md。

**入口**：
```python
def check(
    sizing_result: PositionSizingResult,
    risk_config: RiskConfig,
    execution_config: ExecutionConfig,
    opportunity_grade_config: OpportunityGradeConfig,
    account_risk_state: AccountRiskState,
    plan: TradePlan,
    execution_enabled: bool,
    kill_switch: bool,
    exchange_connected: bool,   # v0.1 恒为 false（无交易所），但检查逻辑完整
    db_healthy: bool,
) -> RiskCheckResult
```

**硬禁止规则（BLOCK）**——任意一条命中即 BLOCK：
1. 无止损（`stop_loss_price is None`）
2. 风险金额超过配置上限（`risk_percent > max_risk_percent`）
3. 杠杆超过配置上限（`leverage > max_leverage`）
4. 止损距离小于最小阈值（`stop_distance_percent < min_stop_distance_percent`）
5. 盈亏比低于最低阈值（`risk_reward_ratio < min_risk_reward_ratio`）
6. 当日亏损达到限制（`daily_loss_r >= daily_loss_limit_r`）
7. 连续亏损达到限制（`consecutive_losses >= max_consecutive_losses`）
8. 冷却期未结束（`now < cooldown_until`）
9. Kill Switch 关闭
10. 交易所/WebSocket 状态异常（v0.1 中 `exchange_connected=false` 仅作 warning，不 BLOCK，因为没有交易所是 v0.1 的正常状态；v0.7 后改为 BLOCK）
11. 数据库无法写入（`db_healthy=false`）
12. 机会等级为 BLOCKED
13. 订单未通过用户确认（v0.1 此项由 decision-gate 处理，risk-engine 跳过）

**降风险规则（REDUCE_RISK）**：
- 机会等级为 B
- 市场结构不完全一致（v0.1 无结构识别，跳过此项；v0.3 后接入）
- 波动率偏高（v0.1 无波动率数据，跳过；v0.2 后接入）
- 计划接近但未达到 A 级
- 最近刚出现亏损（`consecutive_losses > 0`）
- 当前价格偏离入场区（v0.1 无实时价格，跳过；v0.2 后接入）
- 止损距离较宽导致名义仓位较小

**等待规则（WAIT）**：
- 价格尚未进入入场区（v0.1 跳过）
- 需要K线收盘确认（v0.1 跳过）
- 结构未完成（v0.1 跳过）
- 计划等待反抽/回踩（v0.1 跳过）
- AI 评估还未完成（v0.1 跳过）
- 最新行情不足（v0.1 跳过）

v0.1 中 WAIT 规则基本不触发，但逻辑分支保留。

**机会等级与风险权限映射**：
```text
A        → 最高允许配置上限     → status=ALLOW
B        → 降低风险             → status=REDUCE_RISK
C        → 0 风险（不做）       → status=BLOCK
BLOCKED  → 0 风险（禁止）       → status=BLOCK
```

**输出**：
```python
class RiskCheckResult:
    status: RiskStatus              # ALLOW / ALLOW_CONFIRM / WARN / REDUCE_RISK / BLOCK
    risk_amount: Decimal
    notional_value: Decimal
    required_margin: Decimal
    risk_reward_ratio: Decimal
    max_allowed_risk_percent: Decimal
    warnings: list[str]
    block_reasons: list[str]
    config_version: str             # risk_config_version
```

### 3.4 packages/decision-gate

纯函数，无 IO。

**入口**：
```python
def decide(
    risk_result: RiskCheckResult,
    execution_enabled: bool,
    kill_switch: bool,
    ai_evaluation: Optional[AiEvaluation] = None,  # v0.1 恒为 None
    plan_expired: bool = False,
) -> DecisionGateResult
```

**决策逻辑**（v0.1 简化版，无 AI 输入）：
```text
if plan_expired:
    → EXPIRED
if not execution_enabled or kill_switch:
    → BLOCK (reason: execution_disabled / kill_switch_active)
match risk_result.status:
    ALLOW | ALLOW_CONFIRM → ALLOW_CONFIRM
    REDUCE_RISK            → REDUCE_RISK
    WARN                   → WAIT        # 带警告时等待用户调整
    BLOCK                  → BLOCK
```

`aiEvaluation` 入参位保留，v0.5 接入 AI 后在此处合并 AI 建议（但 AI 不能覆盖风控 BLOCK）。

### 3.5 packages/config-versioning

配置版本管理：不可变历史 + 单一激活版本。

**配置类型**：
- `RISK`：max_leverage、min_risk_reward_ratio、preferred_risk_reward_ratio、min_stop_distance_percent、daily_loss_limit_r、max_consecutive_losses、cooldown_minutes_after_loss、max_risk_percent
- `EXECUTION`：enabled、mode（dry_run/live）、margin_mode、allowed_order_types、require_stop_loss、require_user_confirmation、require_second_confirmation
- `OPPORTUNITY_GRADE`：A/B/C/BLOCKED 各自的 max_risk_percent
- `SYMBOL_RULES`：每个 symbol 的 size_step、price_step、min_size、min_notional、max_leverage、fee_rate

**接口**：
```python
def create_version(config_type: ConfigType, payload: dict) -> ConfigVersion
def get_version(version_id: str) -> ConfigVersion
def list_versions(config_type: ConfigType) -> list[ConfigVersion]
def activate_version(version_id: str) -> ConfigVersion  # 同类型仅一个激活
def get_active_version(config_type: ConfigType) -> ConfigVersion
```

版本一旦创建不可修改，只能创建新版本并激活。

---

## 4. 数据库设计

### 4.1 表清单（v0.1 子集）

| 表 | 用途 | 来源 |
|---|---|---|
| `trade_plans` | 交易计划 | DATABASE.md §3.4 |
| `position_sizing_results` | 仓位计算结果 | DATABASE.md §3.5 |
| `risk_checks` | 风控检查结果 | DATABASE.md §3.6 |
| `decision_gate_results` | 决策门结果 | DATABASE.md §3.8 |
| `config_versions` | 配置版本 | DATABASE.md §3.16（隐含） |
| `system_events` | 系统事件审计 | DATABASE.md §3.11 |
| `user_settings` | 用户设置（含 execution_enabled、kill_switch、account_equity） | DATABASE.md §3.17 |
| `account_risk_state` | 账户风险状态（daily_loss_r、consecutive_losses、cooldown_until） | v0.1 新增 |

v0.1 不建表：candles、market_structure_snapshots、candidate_plans、ai_evaluations、order_intents、exchange_orders、order_state_events、positions、trade_journal、review_reports、api_keys。

### 4.2 表结构

字段定义遵循 DATABASE.md，仅做以下 v0.1 调整：

#### trade_plans
```sql
-- 在 DATABASE.md §3.4 基础上：
-- 增加 equity 字段（v0.1 用户手动输入账户权益）
-- status 取值范围：DRAFT / CHECKED / READY_FOR_CONFIRMATION / EXPIRED / CANCELLED
-- 不含后续执行相关状态（SUBMITTING / FILLED 等）
```

#### account_risk_state（v0.1 新增）
```sql
CREATE TABLE account_risk_state (
  id UUID PRIMARY KEY,
  daily_loss_r NUMERIC NOT NULL DEFAULT 0,
  consecutive_losses INTEGER NOT NULL DEFAULT 0,
  cooldown_until TIMESTAMPTZ,
  last_trade_date DATE,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- 单行表，v0.1 恒为初始值；后续版本接入真实成交后更新
```

#### config_versions（v0.1 新增，对齐 DATABASE.md §3.16 隐含设计）
```sql
CREATE TABLE config_versions (
  id UUID PRIMARY KEY,
  config_type VARCHAR(32) NOT NULL,      -- risk / execution / opportunity_grade / symbol_rules
  version_label VARCHAR(64) NOT NULL,    -- 例如 risk-v1
  payload JSONB NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  activated_at TIMESTAMPTZ,
  UNIQUE(config_type, version_label)
);
-- 同一 config_type 仅允许一行 is_active=true（应用层 + 部分唯一索引保证）
CREATE UNIQUE INDEX idx_config_versions_active ON config_versions(config_type) WHERE is_active = true;
```

#### user_settings
```sql
CREATE TABLE user_settings (
  id UUID PRIMARY KEY,
  execution_enabled BOOLEAN NOT NULL DEFAULT false,
  kill_switch BOOLEAN NOT NULL DEFAULT true,   -- 默认安全：关闭
  account_equity NUMERIC,                       -- v0.1 用户手动输入
  mode VARCHAR(32) DEFAULT 'training',          -- training / transition / standard / advanced
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- 单行表
```

#### position_sizing_results / risk_checks / decision_gate_results / system_events
完全遵循 DATABASE.md §3.5 / §3.6 / §3.8 / §3.11 的字段定义。

### 4.3 索引

```sql
CREATE INDEX idx_trade_plans_status ON trade_plans(status, created_at DESC);
CREATE INDEX idx_position_sizing_trade_plan ON position_sizing_results(trade_plan_id);
CREATE INDEX idx_risk_checks_trade_plan ON risk_checks(trade_plan_id);
CREATE INDEX idx_decision_gate_trade_plan ON decision_gate_results(trade_plan_id);
CREATE INDEX idx_system_events_type_time ON system_events(event_type, created_at DESC);
CREATE INDEX idx_config_versions_type_active ON config_versions(config_type, is_active);
```

### 4.4 初始数据（seed）

- `user_settings`：单行，`execution_enabled=false`、`kill_switch=true`、`account_equity=null`、`mode=training`
- `account_risk_state`：单行，全 0/false
- `config_versions`：
  - `risk-v1`（默认风控配置，对齐 USER_TRADING_CONFIG.template.md）
  - `execution-v1`（默认执行配置，dry_run 模式）
  - `opportunity_grade-v1`（A=3% / B=1.5% / C=0 / BLOCKED=0）
  - `symbol_rules-v1`（BTC/ETH/SOL 的常见合约参数）

---

## 5. API 设计

### 5.1 统一响应格式（对齐 API.md §1）

```json
{
  "success": true,
  "data": {},
  "error": null,
  "requestId": "uuid"
}
```

错误：
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RISK_BLOCKED",
    "message": "当前计划未通过风控检查",
    "details": {}
  },
  "requestId": "uuid"
}
```

### 5.2 端点清单（v0.1 子集）

```text
# 交易计划
POST   /api/trade-plans              # 创建计划（status=DRAFT）
POST   /api/trade-plans/{id}/check   # 跑 sizing + risk + decision gate，保存结果，更新 status
GET    /api/trade-plans              # 列表（支持 status 过滤）
GET    /api/trade-plans/{id}         # 详情（含 sizing/risk/decision 结果）

# 风控（独立调用，不保存）
POST   /api/risk/calculate-position  # 单独算仓位
POST   /api/risk/check               # 单独做风控检查

# 配置版本
GET    /api/configs/active           # 当前激活的所有类型配置
GET    /api/configs?type=risk        # 某类型的历史版本
POST   /api/configs                  # 创建新版本
POST   /api/configs/{id}/activate    # 激活某版本

# 系统
GET    /api/system/status            # executionEnabled / killSwitch / dbHealthy / 最新事件
POST   /api/system/kill-switch       # 开关 Kill Switch（写 system_events）
POST   /api/system/execution-mode    # 开关执行模式（v0.1 仅状态位，无实际执行）
```

### 5.3 关键端点契约

#### POST /api/trade-plans
请求：
```json
{
  "exchange": "bitget",
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entry_price": 62400,
  "stop_loss_price": 61900,
  "take_profit_prices": [63800, 64500],
  "leverage": 10,
  "risk_percent": 1,
  "opportunity_grade": "A",
  "equity": 1500,
  "setup_type": "RANGE_SUPPORT_BOUNCE",
  "margin_mode": "isolated",
  "notes": "可选"
}
```
响应：`TradePlan` 对象（status=DRAFT）。

#### POST /api/trade-plans/{id}/check
无请求体。响应：
```json
{
  "plan": { "id": "...", "status": "READY_FOR_CONFIRMATION" },
  "sizing": { "risk_amount": 15, "notional_value": 1875, ... },
  "risk": { "status": "ALLOW_CONFIRM", "block_reasons": [], ... },
  "decision": { "result": "ALLOW_CONFIRM", "reasons": [] }
}
```

#### POST /api/risk/calculate-position
请求：`{ equity, risk_percent, entry_price, stop_loss_price, take_profit_prices, leverage, fee_rate, direction, symbol }`。
响应：`PositionSizingResult`。不落库。

#### POST /api/risk/check
请求：`{ plan, sizing_result }`。响应：`RiskCheckResult`。不落库。

#### GET /api/system/status
响应：
```json
{
  "execution_enabled": false,
  "kill_switch": true,
  "db_healthy": true,
  "latest_event": { "event_type": "KILL_SWITCH_TOGGLED", "created_at": "..." }
}
```

#### POST /api/system/kill-switch
请求：`{ enabled: false }`。写 system_events。响应：更新后的 user_settings。

---

## 6. 前端设计

### 6.1 v0.1 页面清单（从 FRONTEND_PAGES.md 裁剪）

| 页面 | 路由 | 用途 |
|---|---|---|
| Trade Plans | `/plans` | 交易计划中心：创建、检查、列表、详情 |
| Risk Center | `/risk` | 风控状态、配置版本管理、Kill Switch |
| Settings | `/settings` | 账户权益、风控/执行/机会等级/symbol rules 配置编辑器 |

v0.1 不实现：Dashboard、Opportunity Radar、Chart Workspace、Order Preview、Execution Monitor、Journal、Review。

### 6.2 页面布局

#### Trade Plans（/plans）
```text
┌─────────────────────────────────────────────────────┐
│  顶部导航：Trade Plans | Risk Center | Settings      │
│  右上角：Kill Switch 状态灯 | Execution Mode 开关     │
├─────────────────────────┬───────────────────────────┤
│  左：计划列表            │  右：计划详情/创建表单     │
│  - 筛选 status          │  - 创建计划表单            │
│  - 按 created_at 倒序   │    (symbol/direction/      │
│  - 每条显示              │     entry/stop/tp/         │
│    symbol|direction|     │     leverage/risk%/        │
│    RR|grade|status       │     equity/grade)          │
│  - 点击选中              │  - 选中计划详情            │
│                         │    (sizing结果/risk结果/   │
│                         │     decision结果/          │
│                         │     "检查"按钮)            │
└─────────────────────────┴───────────────────────────┘
```

创建表单字段：exchange（默认 bitget）、symbol、direction（LONG/SHORT）、entry_price、stop_loss_price、take_profit_prices（多个，动态添加）、leverage、risk_percent、opportunity_grade（A/B/C）、equity（预填 user_settings）、setup_type、margin_mode、notes。

"检查"按钮调用 `POST /api/trade-plans/{id}/check`，结果就地展示 sizing / risk / decision 三块卡片。

#### Risk Center（/risk）
- 当前激活的风控配置展示（max_leverage、min_rr、daily_loss_limit_r 等）
- 当前账户风险状态展示（dailyLossR、consecutiveLosses、cooldownUntil）
- Kill Switch 状态 + 开关按钮
- Execution Mode 状态 + 开关按钮
- 最近 N 条风控拦截事件（从 system_events 查 severity=warning/block 的）
- 配置版本管理：查看历史版本、创建新版本、激活版本（Tabs 切换 risk/execution/opportunity_grade/symbol_rules）

#### Settings（/settings）
- 账户权益输入（存 user_settings.account_equity）
- 风控配置编辑器（YAML 表单，创建新版本）
- 执行配置编辑器（margin_mode、allowed_order_types、require_stop_loss 等）
- 机会等级配置编辑器（A/B/C/BLOCKED 的 max_risk_percent）
- Symbol rules 编辑器（精度规则，默认填 BTC/ETH/SOL）

### 6.3 前端技术细节

| 项 | 选型 |
|---|---|
| 路由 | Next.js App Router（`app/plans/page.tsx`、`app/risk/page.tsx`、`app/settings/page.tsx`） |
| 渲染 | Client Components + TanStack Query（本地单用户、实时交互，不做 SSR/SSG） |
| API client | `lib/api.ts`，手写 TypeScript 类型与后端 Pydantic 对齐 |
| 表单校验 | zod schema，与后端 Pydantic 校验规则保持一致 |
| 状态 | Zustand（存 Kill Switch、Execution Mode 全局状态） |
| 代理 | Next.js rewrites：`/api/*` → `http://localhost:8000/api/*` |

---

## 7. 验收标准（对齐 MVP_ACCEPTANCE.md v0.1）

### 7.1 必须满足

- [ ] 可以创建交易计划
- [ ] 可以输入入场价、止损价、止盈价
- [ ] 可以计算风险金额
- [ ] 可以计算止损距离
- [ ] 可以计算名义仓位
- [ ] 可以计算保证金
- [ ] 可以计算盈亏比
- [ ] 可以输出风控结论
- [ ] 可以保存计划
- [ ] 单元测试覆盖核心计算

### 7.2 不通过条件（作为测试用例）

- [ ] 仓位计算错误 → 测试用例验证公式正确性
- [ ] 无止损仍可通过 → 测试用例：stop_loss_price=null → BLOCK
- [ ] 超杠杆仍可通过 → 测试用例：leverage > max_leverage → BLOCK
- [ ] 风控结果未保存 → 集成测试：check 后查 risk_checks 表非空

### 7.3 额外验收点（v0.1 完整实现）

- [ ] 精度圆整生效（rounded_size 按 size_step 取整，校验 min_size / min_notional）
- [ ] 当日亏损限制检查生效（手动构造 account_risk_state.daily_loss_r >= limit → BLOCK）
- [ ] 连亏限制检查生效（手动构造 consecutive_losses >= max → BLOCK）
- [ ] 冷却期检查生效（手动构造 cooldown_until > now → BLOCK）
- [ ] Kill Switch 关闭时 BLOCK
- [ ] Execution Mode 关闭时 decision-gate 输出 BLOCK
- [ ] 配置版本激活后立即生效（新 check 使用新配置）
- [ ] 机会等级 A/B/C/BLOCKED 风险权限映射正确
- [ ] decision-gate 五种状态（ALLOW_CONFIRM/WAIT/REDUCE_RISK/BLOCK/EXPIRED）均可触发
- [ ] system_events 记录 Kill Switch 切换、配置激活事件

---

## 8. 项目初始化方案

### 步骤 1：基础设施
- `f:\crypto\docker-compose.yml`：PostgreSQL 16 + volume
- `f:\crypto\.env.example`：DATABASE_URL、API_PORT、NODE_ENV
- `f:\crypto\.gitignore`：node_modules、.venv、__pycache__、.env、.superpowers/

### 步骤 2：Python workspace
- 根 `pyproject.toml`（uv workspace 定义）
- `packages/shared/`、`packages/position-sizing/`、`packages/risk-engine/`、`packages/decision-gate/`、`packages/config-versioning/` 各自 `pyproject.toml`
- `apps/api/` FastAPI 应用 + Alembic

### 步骤 3：前端
- `apps/web/` Next.js 14（pnpm）
- shadcn/ui 初始化
- 3 个页面骨架 + API client

### 步骤 4：开发流程
- `docker compose up -d postgres` 起数据库
- `apps/api`：`uv run alembic upgrade head` → `uv run uvicorn main:app --reload --port 8000`
- `apps/web`：`pnpm dev`（默认 3000 端口）
- 前端调后端 `http://localhost:8000`，Next.js rewrites 代理 `/api/*`

---

## 9. 风险与注意事项

1. **风控引擎是核心**：所有计算和检查逻辑必须 100% 单元测试覆盖。任何修改必须先过测试。
2. **配置版本不可变**：已创建的配置版本不能修改，只能创建新版本并激活。这保证风控结论可复盘。
3. **Kill Switch 默认开启**：`user_settings.kill_switch` 初始为 true，`execution_enabled` 初始为 false。用户必须主动开启才能进入确认流程。
4. **v0.1 不接交易所**：`exchange_connected` 恒为 false。risk-engine 中此项仅作 warning（不 BLOCK），因为 v0.1 的正常状态就是没有交易所。v0.7 接入后改为 BLOCK。
5. **decimal 精度**：所有金额、价格、数量计算使用 Python `Decimal`，不使用 `float`。数据库字段用 `NUMERIC`。
6. **时区**：所有时间戳用 UTC 存储和传输，前端展示时转本地时区。

---

## 10. 后续版本衔接点

| 后续版本 | v0.1 预留的扩展点 |
|---|---|
| v0.2 | 新增 `packages/market-data`，`apps/api` 增加 `/api/market/*` 端点，`apps/web` 增加 Chart Workspace 页面 |
| v0.3 | 新增 `packages/market-structure`，`market_structure_snapshots` 表 |
| v0.4 | 新增 `packages/auto-plan-engine`，`candidate_plans` 表，Opportunity Radar 页面 |
| v0.5 | 新增 `packages/ai-evaluation-agent`，`ai_evaluations` 表，decision-gate 的 `aiEvaluation` 入参填充 |
| v0.6 | 新增 `packages/execution-engine`，`order_intents` 表，Order Preview 页面 |
| v0.7 | 新增 `packages/exchange-adapters`（BitgetAdapter），symbol_rules 改为交易所同步 |
| v0.8 | execution-engine 接入真实下单，account_risk_state 接入真实成交更新 |
| v1.0 | 补齐 Dashboard / Journal / Review 等页面，完整 L4 闭环 |

---

## 附录 A：默认配置（seed 数据）

### risk-v1
```yaml
max_risk_percent: 3
max_leverage: 10
min_risk_reward_ratio: 1.5
preferred_risk_reward_ratio: 2.0
min_stop_distance_percent: 0.3
daily_loss_limit_r: 2
max_consecutive_losses: 2
cooldown_minutes_after_loss: 30
```

### execution-v1
```yaml
enabled: false
mode: dry_run
margin_mode: isolated
allowed_order_types:
  - limit
require_stop_loss: true
require_user_confirmation: true
require_second_confirmation: true
```

### opportunity_grade-v1
```yaml
A:
  max_risk_percent: 3
B:
  max_risk_percent: 1.5
C:
  max_risk_percent: 0
BLOCKED:
  max_risk_percent: 0
```

### symbol_rules-v1
```yaml
BTCUSDT:
  size_step: "0.001"
  price_step: "0.1"
  min_size: "0.001"
  min_notional: "5"
  max_leverage: 100
  fee_rate: "0.0005"
ETHUSDT:
  size_step: "0.01"
  price_step: "0.01"
  min_size: "0.01"
  min_notional: "5"
  max_leverage: 100
  fee_rate: "0.0005"
SOLUSDT:
  size_step: "0.1"
  price_step: "0.001"
  min_size: "0.1"
  min_notional: "5"
  max_leverage: 75
  fee_rate: "0.0005"
```
