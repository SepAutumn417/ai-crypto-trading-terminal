# 事件日志与审计设计

## 1. 目标

系统不仅要记录交易结果，还要记录交易过程。

事件日志用于回答：

- 系统何时发现机会；
- 系统为什么允许或禁止；
- 用户是否忽略警告；
- 订单如何提交；
- 交易所返回了什么；
- 风控何时触发；
- Kill Switch何时打开/关闭。

---

## 2. 事件类型

| 类型 | 说明 |
|---|---|
| `MARKET_DATA_SYNCED` | 行情同步完成 |
| `STRUCTURE_SNAPSHOT_CREATED` | 结构快照生成 |
| `CANDIDATE_PLAN_DISCOVERED` | 发现候选计划 |
| `PLAN_CREATED` | 创建交易计划 |
| `PLAN_UPDATED` | 修改交易计划 |
| `RISK_CHECK_COMPLETED` | 风控检查完成 |
| `RISK_BLOCKED` | 风控禁止 |
| `AI_EVALUATION_CREATED` | AI评估生成 |
| `DECISION_GATE_RESULT` | 决策门输出 |
| `ORDER_PREVIEW_CREATED` | 订单预览生成 |
| `ORDER_CONFIRMED_BY_USER` | 用户确认订单 |
| `ORDER_SUBMITTING` | 订单提交中 |
| `ORDER_ACCEPTED` | 交易所接受订单 |
| `ORDER_REJECTED` | 交易所拒绝订单 |
| `ORDER_FILLED` | 订单成交 |
| `TP_SL_PLACED` | 止盈止损设置成功 |
| `TP_SL_FAILED` | 止盈止损设置失败 |
| `KILL_SWITCH_TRIGGERED` | Kill Switch触发 |
| `CONFIG_VERSION_CHANGED` | 配置变更 |
| `JOURNAL_CREATED` | 日志创建 |
| `REVIEW_COMPLETED` | 复盘完成 |

---

## 3. 事件字段

```json
{
  "eventId": "uuid",
  "eventType": "RISK_BLOCKED",
  "severity": "INFO | WARNING | ERROR | CRITICAL",
  "entityType": "trade_plan | order | position | config",
  "entityId": "uuid",
  "message": "",
  "payload": {},
  "actor": "system | user | exchange | ai",
  "createdAt": "2026-07-07T10:00:00Z"
}
```

---

## 4. 审计事件

以下操作必须作为审计事件记录：

- API Key更新；
- Execution Mode开启/关闭；
- Kill Switch手动关闭/开启；
- 风控配置变更；
- 用户确认真实下单；
- 用户撤销订单；
- 用户绕过警告尝试；
- 系统自动降级。

---

## 5. 日志存储策略

- 普通事件长期保存；
- 请求响应敏感字段脱敏；
- 订单执行日志不可删除，只能标记废弃；
- 配置变更日志永久保存。

---

## 6. 事件用途

- 复盘分析；
- 风控优化；
- 调试问题；
- 追踪异常订单；
- 判断系统是否稳定；
- 判断用户是否违反纪律。
