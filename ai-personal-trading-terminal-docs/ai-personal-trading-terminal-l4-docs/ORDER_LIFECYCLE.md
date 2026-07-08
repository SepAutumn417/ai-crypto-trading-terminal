# 订单生命周期设计

## 1. 订单状态机

```text
DRAFT
  ↓
RISK_CHECKED
  ↓
AI_EVALUATED
  ↓
READY_FOR_CONFIRMATION
  ↓
CONFIRMED_BY_USER
  ↓
SUBMITTING
  ↓
SUBMITTED
  ↓
ACCEPTED_BY_EXCHANGE
  ↓
PARTIALLY_FILLED / FILLED / CANCELLED / REJECTED / FAILED
  ↓
TP_SL_PLACING
  ↓
TP_SL_PLACED
  ↓
POSITION_MONITORING
  ↓
CLOSING / CLOSED
  ↓
JOURNAL_CREATED
  ↓
REVIEWED
```

---

## 2. 状态定义

| 状态 | 说明 |
|---|---|
| `DRAFT` | 内部订单草稿 |
| `RISK_CHECKED` | 已完成风控检查 |
| `AI_EVALUATED` | 已完成AI评估 |
| `READY_FOR_CONFIRMATION` | 可进入用户确认 |
| `CONFIRMED_BY_USER` | 用户已确认 |
| `SUBMITTING` | 正在提交交易所 |
| `SUBMITTED` | 请求已发送 |
| `ACCEPTED_BY_EXCHANGE` | 交易所接受订单 |
| `PARTIALLY_FILLED` | 部分成交 |
| `FILLED` | 完全成交 |
| `CANCELLED` | 已撤单 |
| `REJECTED` | 交易所拒绝 |
| `FAILED` | 系统或网络失败 |
| `TP_SL_PLACING` | 正在设置止盈止损 |
| `TP_SL_PLACED` | 止盈止损设置成功 |
| `POSITION_MONITORING` | 持仓监控中 |
| `CLOSING` | 正在平仓 |
| `CLOSED` | 已关闭 |
| `JOURNAL_CREATED` | 已生成日志 |
| `REVIEWED` | 已复盘 |

---

## 3. 状态转换规则

### 3.1 DRAFT → RISK_CHECKED

条件：

- 订单草稿包含完整参数；
- 入场价、止损价、数量存在；
- 风控引擎完成检查。

### 3.2 RISK_CHECKED → READY_FOR_CONFIRMATION

条件：

- 风控结果为 `ALLOW` 或 `ALLOW_CONFIRM`；
- AI评估已完成；
- Execution Enabled为true；
- Kill Switch未触发。

### 3.3 READY_FOR_CONFIRMATION → CONFIRMED_BY_USER

条件：

- 用户点击确认；
- 高风险订单完成二次确认；
- 用户会话有效。

### 3.4 CONFIRMED_BY_USER → SUBMITTING

条件：

- 再次检查风控；
- 再次检查账户权益；
- 再次检查计划未过期；
- 生成clientOid。

### 3.5 SUBMITTING → SUBMITTED

条件：

- 请求已发送到交易所API。

### 3.6 SUBMITTED → ACCEPTED_BY_EXCHANGE

条件：

- 交易所返回orderId或成功状态。

### 3.7 FILLED → TP_SL_PLACING

条件：

- 开仓订单已成交；
- 需要独立设置止盈止损。

### 3.8 TP_SL_PLACING → TP_SL_PLACED

条件：

- 止盈止损订单设置成功；
- 或开仓订单已带预设TP/SL且确认存在。

---

## 4. 异常状态

### 4.1 REJECTED

交易所明确拒绝订单。

处理：

- 记录拒绝原因；
- 不重试；
- 显示给用户。

### 4.2 FAILED

系统失败或网络不确定。

处理：

- 查询交易所订单状态；
- 禁止盲目重试；
- 必要时触发Kill Switch。

### 4.3 TP_SL_FAILED

止盈止损设置失败。

> 此规则与 `EXECUTION_SAFETY.md §8`、`OPERATIONS.md §3.3` 保持一致：**止损设置失败 → 立即触发 Kill Switch（`kill_switch = true`）+ 记录 CRITICAL 事件 + 禁止新单 + 提供补设止损 UI**。

处理：

- 立即触发 Kill Switch（`kill_switch = true`）；
- 记录 CRITICAL 级别 `system_events`；
- 禁止新单；
- 提示用户人工检查持仓；
- 提供一键补设止损确认 UI。

---

## 5. 订单审计字段

每个订单状态变化都要记录：

- order_intent_id；
- previous_status；
- next_status；
- reason；
- actor：system/user/exchange；
- timestamp；
- raw_payload；
- raw_response；
- request_hash。
