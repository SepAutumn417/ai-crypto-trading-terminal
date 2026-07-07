# 风控规则文档

## 1. 风控引擎定位

风控引擎是系统核心安全模块。

任何交易计划、候选计划、订单预览、真实执行，都必须经过风控引擎。

AI不能覆盖风控结论。

---

## 2. 风控输入

```json
{
  "equity": 1500,
  "riskPercent": 1,
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entryPrice": 62400,
  "stopLossPrice": 61900,
  "takeProfitPrices": [63800, 64500],
  "leverage": 10,
  "setupType": "RANGE_SUPPORT_BOUNCE",
  "opportunityGrade": "A",
  "marketState": "RANGE",
  "dailyLossR": 0,
  "consecutiveLosses": 0,
  "cooldownActive": false,
  "executionEnabled": true
}
```

---

## 3. 核心计算

```text
riskAmount = equity * riskPercent
stopDistancePercent = abs(entryPrice - stopLossPrice) / entryPrice
notionalValue = riskAmount / stopDistancePercent
requiredMargin = notionalValue / leverage
riskRewardRatio = takeProfitDistance / stopDistance
```

---

## 4. 风控结果

```json
{
  "status": "ALLOW_CONFIRM",
  "riskAmount": 15,
  "notionalValue": 1875,
  "requiredMargin": 187.5,
  "riskRewardRatio": 2.0,
  "maxAllowedRiskPercent": 1,
  "warnings": [],
  "blockReasons": [],
  "configVersion": "risk-v1"
}
```

---

## 5. 硬性禁止规则

出现以下任意情况，直接 `BLOCK`：

1. 无止损；
2. 风险金额超过配置上限；
3. 杠杆超过配置上限；
4. 止损距离小于最小阈值；
5. 盈亏比低于最低阈值；
6. 当日亏损达到限制；
7. 连续亏损达到限制；
8. 冷却期未结束；
9. Kill Switch关闭；
10. WebSocket/交易所状态异常；
11. 数据库无法写入；
12. 机会等级为禁止；
13. 订单未通过用户确认。

---

## 6. 降风险规则

出现以下情况，输出 `REDUCE_RISK`：

- 机会等级为B；
- 市场结构不完全一致；
- 波动率偏高；
- 计划接近但未达到A级；
- 最近刚出现亏损；
- 当前价格偏离入场区；
- 止损距离较宽导致名义仓位较小。

---

## 7. 等待规则

输出 `WAIT` 的情况：

- 价格尚未进入入场区；
- 需要K线收盘确认；
- 结构未完成；
- 计划等待反抽/回踩；
- AI评估还未完成；
- 最新行情不足。

---

## 8. 机会评级与风险权限

| 等级 | 风险权限 | 执行状态 |
|---|---:|---|
| A | 最高允许配置上限 | 可进入确认 |
| B | 降低风险 | 可观察或小风险确认 |
| C | 0 | 不做 |
| BLOCKED | 0 | 禁止 |

---

## 9. 动态风险模式

系统支持根据账户权益动态计算风险金额。

示例：

```text
riskAmount = currentEquity * riskPercent
```

注意：

- 使用已实现权益，不使用未平仓浮盈放大风险；
- 可以配置是否使用浮动权益；
- 建议默认使用账户可用权益或净权益的保守值。

---

## 10. 配置版本

每次风控计算必须记录：

- risk_config_version；
- user_trading_config_version；
- strategy_config_version；
- calculation_payload_hash。
