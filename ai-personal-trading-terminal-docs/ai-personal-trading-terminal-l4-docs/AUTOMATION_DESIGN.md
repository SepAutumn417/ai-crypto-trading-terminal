# 自动化设计文档

## 1. 目标

自动化系统的目标是减少人工判断和手动输入错误，但不取消用户最终确认。

系统需要自动完成：

- 市场扫描；
- 结构识别；
- 候选机会发现；
- 计划生成；
- 仓位计算；
- 风控审核；
- AI评估；
- 订单参数准备。

---

## 2. 自动机会雷达

### 2.1 功能

自动扫描自选标的，生成候选交易计划列表。

### 2.2 输入

- 自选标的；
- 周期配置；
- K线数据；
- 当前价格；
- 市场结构快照；
- 风控配置；
- 当前账户状态；
- 今日交易状态。

### 2.3 输出

```json
{
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "setupType": "RANGE_SUPPORT_BOUNCE",
  "entryZone": [62400, 62800],
  "stopLoss": 61900,
  "targets": [63800, 64500],
  "riskReward": 2.1,
  "grade": "A",
  "status": "WATCHING",
  "maxAllowedRiskPercent": 3
}
```

---

## 3. 候选计划类型

| 类型 | 说明 |
|---|---|
| `TREND_PULLBACK_LONG` | 上升趋势回踩做多 |
| `TREND_PULLBACK_SHORT` | 下降趋势反抽做空 |
| `RANGE_SUPPORT_BOUNCE` | 震荡区间下沿反弹 |
| `RANGE_RESISTANCE_REJECT` | 震荡区间上沿受阻 |
| `BREAKOUT_RETEST_LONG` | 突破后回踩确认做多 |
| `BREAKDOWN_RETEST_SHORT` | 跌破后反抽确认做空 |
| `FALSE_BREAK_REVERSAL` | 假突破后反向计划 |

---

## 4. 候选计划状态机

```text
DISCOVERED
  ↓
WATCHING
  ↓
READY
  ↓
RISK_CHECKED
  ↓
AI_EVALUATED
  ↓
ALLOW_CONFIRM / WAIT / BLOCK / EXPIRED
```

### 状态说明

| 状态 | 说明 |
|---|---|
| `DISCOVERED` | 系统发现潜在机会 |
| `WATCHING` | 进入观察状态，等待触发 |
| `READY` | 入场条件接近满足 |
| `RISK_CHECKED` | 已完成风控检查 |
| `AI_EVALUATED` | 已完成AI评估 |
| `ALLOW_CONFIRM` | 允许用户确认执行 |
| `WAIT` | 条件不足，继续等待 |
| `BLOCK` | 风控禁止 |
| `EXPIRED` | 计划失效 |

---

## 5. 实时评估机制

### 5.1 算法实时运行

算法可在以下频率运行：

- tick级价格监控；
- K线收盘后结构更新；
- 计划触发条件检查；
- 风控状态检查。

### 5.2 AI事件触发

AI不应每秒调用，而应事件驱动。

触发条件：

- 新K线收盘；
- 新候选计划生成；
- 计划进入READY；
- 风控结论变化；
- 订单进入预览；
- 用户尝试确认执行；
- 持仓偏离计划；
- 交易结束复盘。

---

## 6. 自动仓位计算

系统自动读取或输入账户权益，根据配置计算风险金额。

核心公式：

```text
riskAmount = equity * riskPercent
stopDistancePercent = abs(entryPrice - stopLossPrice) / entryPrice
notionalValue = riskAmount / stopDistancePercent
requiredMargin = notionalValue / leverage
```

执行前必须再经过交易所精度和最小下单量处理。

---

## 7. 自动化输出原则

系统输出的是 **候选计划**，不是无条件买卖信号。

正确输出：

```text
BTCUSDT出现B级观察计划，等待15m收盘确认后可进入订单预览。
```

错误输出：

```text
马上买入BTC。
```

---

## 8. 决策门

所有自动化结果必须经过 Decision Gate。

Decision Gate 输出：

- `ALLOW_CONFIRM`；
- `WAIT`；
- `REDUCE_RISK`；
- `BLOCK`；
- `EXPIRED`。

只有 `ALLOW_CONFIRM` 可以进入 `Order Preview`。

---

## 9. 候选计划 ↔ 订单意图状态映射

> 候选计划状态机（§4）与订单意图状态机（`ORDER_LIFECYCLE.md §1`）都有 `RISK_CHECKED / AI_EVALUATED`，但语义不同：候选计划侧是"预检查"，订单意图侧是"正式检查落库"。promote 时需做状态映射。

| 候选计划状态 | → promote 后订单意图初始状态 | 说明 |
|---|---|---|
| `DISCOVERED` / `WATCHING` | 不可 promote | 候选计划未就绪 |
| `READY` | `DRAFT` | promote 后从 DRAFT 起重新走正式风控/AI/决策门 |
| `RISK_CHECKED` | `DRAFT` | 候选侧的预检查不复用，promote 后重新 check |
| `AI_EVALUATED` | `DRAFT` | 同上，AI 评估需基于正式 trade_plan 重跑 |
| `ALLOW_CONFIRM` | `READY_FOR_CONFIRMATION` | 候选侧已确认可执行，promote 后直接进入确认态（但仍需用户在订单预览页二次确认） |
| `WAIT` / `BLOCK` | 不可 promote | 候选计划未通过 |
| `EXPIRED` | 不可 promote | 已失效 |

---

## 10. Promote 流程

`POST /api/auto-plans/{id}/promote` 把候选计划提升为正式交易计划。

流程：

1. 校验候选计划 `status` ∈ {`READY`, `RISK_CHECKED`, `AI_EVALUATED`, `ALLOW_CONFIRM`}，否则返回 `PLAN_STATUS_ERROR`；
2. 复制字段：`exchange / symbol / direction / setup_type / entry_price / stop_loss_price / take_profit_prices / risk_reward_ratio / opportunity_grade` 从 `candidate_plans` 复制到新 `trade_plans` 行；
3. `trade_plans.candidate_plan_id` 写入原候选计划 id（外键关联）；
4. 候选计划 `status` 置为 `PROMOTED`（新增状态，表示已提升，防止重复 promote）；
5. 候选计划后续状态变化**不影响**已 promote 的 trade_plan（字段已复制，非引用）；
6. `trade_plans.status` 按 §9 映射表设置初始状态；
7. 整个 promote 在单事务内完成。

> 字段复制而非引用：保证候选计划失效/调整后，已 promote 的正式计划参数不变，可复盘。
