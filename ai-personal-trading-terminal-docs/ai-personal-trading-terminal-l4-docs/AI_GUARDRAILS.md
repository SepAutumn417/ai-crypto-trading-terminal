# AI边界与防护设计

## 1. AI定位

AI是解释器、审查员、复盘助手，不是交易执行主体。

AI负责：

- 解释市场结构；
- 解释候选计划；
- 解释风控结果；
- 生成等待条件；
- 标记潜在情绪风险；
- 生成复盘总结。

AI不负责：

- 直接下单；
- 绕过风控；
- 修改风控配置；
- 建议无止损交易；
- 建议超过系统限制的仓位或杠杆。

---

## 2. AI输入必须结构化

AI输入应来自系统已计算结果，而不是让AI自由读取一堆原始信息。

```json
{
  "marketStructure": {},
  "candidatePlan": {},
  "riskResult": {},
  "recentTradeState": {},
  "systemMode": "L4_CONFIRM_EXECUTION"
}
```

---

## 3. AI输出必须结构化

AI必须返回JSON格式。

```json
{
  "summary": "",
  "marketStateExplanation": "",
  "planQualityExplanation": "",
  "riskExplanation": "",
  "opportunityGradeComment": "",
  "recommendedAction": "WAIT | ALLOW_CONFIRM | REDUCE_RISK | DO_NOT_TRADE",
  "warnings": [],
  "upgradeConditions": [],
  "invalidationConditions": [],
  "emotionalRiskFlags": []
}
```

---

## 4. AI不得输出

AI不得输出：

- “直接满仓”；
- “不用止损”；
- “加大杠杆追回”；
- “忽略系统风控”；
- “现在必须买/卖”；
- “风控禁止但我建议继续”；
- “保证盈利”。

---

## 5. AI与风控冲突处理

如果AI输出与风控冲突：

- 以风控为准；
- AI输出标记为冲突；
- 写入事件日志；
- 不允许进入执行。

---

## 6. AI调用时机

AI调用应事件驱动：

- 新结构快照生成；
- 新候选计划生成；
- 计划进入READY；
- 风控结果变化；
- 用户进入订单预览；
- 订单执行结束；
- 日终复盘。

---

## 7. AI复盘职责

AI复盘应回答：

1. 是否按计划执行；
2. 是否违反风控；
3. 是否存在情绪化交易；
4. 计划逻辑是否失效；
5. 止损是否合理；
6. 是否应优化规则。

---

## 8. AI安全提示

所有AI输出都应附带系统级提示：

> 该评估基于当前数据和规则，不构成盈利保证。真实交易必须以风控引擎和用户确认结果为准。
