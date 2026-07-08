# 系统设计文档

## 1. 总体架构

> 分层视图对齐 `MODULES.md §1` 的 13 个 packages。表现层 → API 编排层 → 领域纯逻辑层 → 适配层 → 基础设施。

```text
┌─────────────────────────────────────────────────────────────┐
│                      表现层 (apps/web)                       │
│  Dashboard / Radar / Chart / Plans / Risk / Journal / Review │
└───────────────────────────────┬─────────────────────────────┘
                                │  REST + WebSocket
┌───────────────────────────────▼─────────────────────────────┐
│                  API 编排层 (apps/api)                       │
│  Auth / Config / Plans / Risk / AI / Execute / System        │
│  services: plan / config / execution / journal / market      │
└───────────────────────────────┬─────────────────────────────┘
                                │
        ┌───────────┬───────────┼───────────┬────────────┐
        │           │           │           │            │
┌───────▼──────┐ ┌──▼────────┐ ┌▼──────────┐ ┌▼─────────┐ ┌▼────────────┐
│ market-data  │ │ market-   │ │auto-plan-  │ │ position- │ │ ai-         │
│              │ │ structure │ │ engine     │ │ sizing    │ │ evaluator   │
└──────┬───────┘ └──┬────────┘ └──┬─────────┘ └──┬───────┘ └──┬──────────┘
       │            │             │              │            │
       │     ┌──────▼──────┐ ┌────▼────────┐ ┌───▼──────┐ ┌───▼──────┐
       │     │ risk-engine │ │decision-gate│ │ journal  │ │ review   │
       │     └──────┬──────┘ └─────┬───────┘ └────┬─────┘ └────┬─────┘
       │            │              │              │            │
┌──────▼────────────▼──────────────▼──────────────▼────────────▼─────────┐
│                       领域纯逻辑层 (packages/*)                          │
│  shared / position-sizing / risk-engine / decision-gate /                │
│  config-versioning / event-log / market-data / market-structure /        │
│  auto-plan-engine / ai-evaluator / journal / review                      │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                     适配层 (exchange-adapters)               │
│              BitgetAdapter (first) / MockExchange            │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│                       基础设施                               │
│        PostgreSQL 16 / Redis / Docker Compose                │
│  Candles / Plans / Orders / Events / Snapshots / Configs     │
└─────────────────────────────────────────────────────────────┘
```

> 说明：领域纯逻辑层中的 `risk-engine / position-sizing / decision-gate` 为无 IO 纯函数包，可独立单测；`market-data / market-structure / auto-plan-engine / ai-evaluator / journal / review / config-versioning / event-log` 为有状态/有 IO 的领域包；`exchange-adapters` 屏蔽交易所 API 差异。

---

## 2. 核心设计原则

### 2.1 风控先行

所有交易计划和订单请求必须经过 `Risk Engine` 与 `Decision Gate`。

任何模块不得直接调用交易所执行接口。

### 2.2 AI受控

AI只接收结构化上下文，并输出结构化评估。

AI不拥有订单执行权限。

### 2.3 执行可回滚

交易所执行必须支持：

- 幂等请求；
- 状态机；
- 撤单；
- Kill Switch；
- 异常回退；
- Dry Run。

### 2.4 配置有版本

每个交易计划、风控结果、订单执行都必须记录对应配置版本。

---

## 3. 服务拆分

## 3.1 Web App

职责：

- 展示行情、结构、计划、风控、AI评估；
- 让用户创建/确认/取消计划；
- 展示订单预览；
- 展示持仓和交易日志。

建议技术：

- Next.js 或 React；
- Tailwind CSS；
- TradingView Lightweight Charts；
- Zustand 或 Redux Toolkit。

## 3.2 API Server

职责：

- 提供REST API；
- 管理用户配置；
- 调用内部服务；
- 做权限检查；
- 统一记录事件日志。

建议技术：

- FastAPI 或 NestJS；
- PostgreSQL；
- Redis；
- Docker Compose。

## 3.3 Market Data Service

职责：

- 拉取K线；
- 订阅实时行情；
- 写入 candles；
- 发布行情事件。

## 3.4 Market Structure Engine

职责：

- 识别 Swing High / Low；
- 识别趋势和震荡；
- 识别BOS/CHOCH；
- 生成关键位；
- 输出结构快照。

## 3.5 Auto Plan Engine

职责：

- 根据结构生成候选计划；
- 给出入场区、止损、目标；
- 计算初始盈亏比；
- 生成计划状态。

## 3.6 Position Sizing Engine

职责：

- 当前权益读取；
- 风险金额计算；
- 止损距离计算；
- 名义仓位计算；
- 合约数量换算；
- 精度适配。

## 3.7 Risk Engine

职责：

- 单笔风险检查；
- 杠杆检查；
- 止损检查；
- 盈亏比检查；
- 日亏损检查；
- 连亏检查；
- 冷却期检查；
- 风控结论输出。

## 3.8 AI Evaluation Agent

职责：

- 基于市场结构、候选计划和风控结果生成解释；
- 输出固定JSON；
- 不参与最终风控判定；
- 不直接执行交易。

## 3.9 Decision Gate

职责：

综合结构、计划、风控、AI评估，输出最终状态：

- `ALLOW_CONFIRM`；
- `WAIT`；
- `REDUCE_RISK`；
- `BLOCK`；
- `EXPIRED`。

只有 `ALLOW_CONFIRM` 才能进入订单预览。

## 3.10 Execution Engine

职责：

- 生成交易所订单请求；
- 执行Dry Run；
- 提交订单；
- 设置止盈止损；
- 撤单；
- 同步订单状态；
- 写执行日志。

## 3.11 Exchange Adapter

职责：

抽象交易所API差异。

第一适配器：Bitget。

接口包括：

- getAccountEquity；
- getPositions；
- placeOrder；
- cancelOrder；
- placeTpSl；
- subscribeOrders；
- subscribePositions；
- getSymbolRules。

---

## 4. 数据流

## 4.1 自动候选计划数据流

```text
Market Data → Structure Snapshot → Auto Plan Engine → Candidate Plans → Risk Precheck → AI Evaluation → Opportunity Radar
```

## 4.2 L4执行数据流

```text
Candidate Plan / Manual Plan
  ↓
Position Sizing
  ↓
Risk Engine
  ↓
AI Evaluation
  ↓
Decision Gate
  ↓
Order Preview
  ↓
User Confirmation
  ↓
Execution Engine
  ↓
Exchange API
  ↓
Order Monitor
  ↓
Journal
```

---

## 5. 状态管理

系统至少要管理以下状态：

- 系统模式；
- 执行开关；
- 风控状态；
- 市场结构状态；
- 候选计划状态；
- 订单状态；
- 持仓状态；
- AI评估状态；
- 交易日志状态。

---

## 6. 可扩展点

| 扩展点 | 当前实现 | 后续扩展 |
|---|---|---|
| 交易所 | Bitget | Binance/OKX等 |
| AI供应商 | API调用 | 多模型路由/本地模型 |
| 市场结构 | 规则算法 | 订单流/清算/OI增强 |
| 风控规则 | 配置驱动 | 策略级风控模板 |
| 执行 | L4确认执行 | 后续受限L5实验 |
