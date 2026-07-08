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

### 单位约定

| 字段 | 单位 | 示例 | 说明 |
|---|---|---|---|
| `riskPercent` | 百分数基 | `1` = 1% | 配置中 `max_risk_percent`、`risk_percent` 均为百分数基 |
| `stopDistancePercent` | 小数 | `0.008` = 0.8% | 计算结果为小数，比较时需乘 100 转为百分数基 |
| `min_stop_distance_percent` | 百分数基 | `0.3` = 0.3% | 配置项使用百分数基，与 `riskPercent` 一致 |
| `max_notional_equity_ratio` | 倍数 | `20` = 20倍 | 名义价值 / 账户权益的上限倍数 |

---

## 4. 风控结果

> 风控引擎（risk-engine）只输出 `ALLOW / WARN / REDUCE_RISK / BLOCK` 四种状态。`ALLOW_CONFIRM / WAIT / EXPIRED` 属于决策门（decision-gate）的输出，详见 `MODULES.md §10` 与 `AUTOMATION_DESIGN.md`。本文 §4 示例展示的是 decision-gate 之后的最终结果。

```json
{
  "status": "ALLOW_CONFIRM",
  "riskAmount": 15,
  "notionalValue": 1872,
  "requiredMargin": 187.2,
  "riskRewardRatio": 2.0,
  "maxAllowedRiskPercent": 1,
  "warnings": [],
  "blockReasons": [],
  "configVersion": "risk-v1"
}
```

> 数值说明：`equity=1500`、`riskPercent=1`、`entry=62400`、`stop=61900` 时，`stop_distance = 500/62400 = 0.0080128…`，`notional = 15 / 0.0080128 = 1872.0`。早期文档示例中 `notionalValue: 1875` 是按 `0.008` 整除得到的近似值，已被 `packages/position-sizing` 的精确计算与 `test_calculate_long_basic` 测试用例修正为 `1872`。

---

## 5. 硬性禁止规则

> Kill Switch 极性约定：`kill_switch = true` 表示 Kill Switch 已激活（熔断态），禁止新开仓；`kill_switch = false` 表示恢复交易。下文规则 9 中的"Kill Switch 激活"即指 `kill_switch = true`。

出现以下任意情况，直接 `BLOCK`：

1. 无止损；
2. 风险金额超过配置上限；
3. 杠杆超过配置上限；
4. 止损距离小于最小阈值（百分数基，如 0.3 = 0.3%）；
5. 盈亏比低于最低阈值；
6. 当日亏损达到限制；
7. 连续亏损达到限制；
8. 冷却期未结束；
9. Kill Switch 激活（`kill_switch = true`）；
10. WebSocket/交易所状态异常（**v0.1 降级说明**：v0.1 无交易所接入，`exchange_connected=false` 属正常状态，本项降级为 warning，不 BLOCK；v0.7 接入 Bitget 后恢复为 BLOCK）；
11. 数据库无法写入；
12. 机会等级为禁止；
13. 订单未通过用户确认；
14. 名义价值 / 账户权益 超过上限（如 20 倍，对应 `max_notional_equity_ratio` 配置项）。

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

## 7. 等待规则（已迁移至决策门）

> `WAIT` 是决策门（DecisionGate）的输出状态，不属于风控引擎（RiskEngine）的输出。RiskEngine 只输出 `ALLOW / WARN / REDUCE_RISK / BLOCK`。以下等待场景由 DecisionGate 综合风控结果、AI 评估、行情状态后判定，详见 `AUTOMATION_DESIGN.md` 与 `MODULES.md §10`。

DecisionGate 输出 `WAIT` 的情况：

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

### 8.1 B 级"小风险确认"路径

B 级机会默认输出 `REDUCE_RISK`，无法直接进入订单预览。允许进入确认的路径：

1. 用户在 `REDUCE_RISK` 结果上手动调低 `risk_percent` 至 B 级上限（默认 1.5%）或更低；
2. 重新调用 `POST /api/trade-plans/{id}/check`；
3. 若新一次风控中 `risk_percent <= opportunity_grade_config.B.max_risk_percent` 且无其他 BLOCK 命中，RiskEngine 仍输出 `REDUCE_RISK`（因为机会等级仍为 B），但 DecisionGate 在用户已主动降险的前提下可输出 `ALLOW_CONFIRM`（需 v0.6+ 决策门增加"用户已降险"标志后启用）。

v0.1 ~ v0.5：B 级永远到不了 `ALLOW_CONFIRM`，只能观察或手动调整后重检。v0.6 起决策门增加 `user_adjusted_reduce_risk` 标志后，B 级在用户主动降险后可进入确认。

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

---

## 11. 当日亏损 R 与冷却期定义

### 11.1 当日亏损 R 计算

```text
当日亏损 R = Σ(当日已平仓交易的 actual_R) + 当日已实现手续费 / risk_amount
```

- `actual_R`：单笔已平仓交易的盈亏倍数，盈利为正、亏损为负（如 -1R 表示亏 1 倍风险金额）；
- 只统计**当日已平仓**交易，未平仓浮亏不计入；
- 手续费按 `已实现手续费 / risk_amount` 折算为 R 值累加；
- `daily_loss_limit_r`（默认 2）：当日亏损 R 达到此值即触发规则 6 BLOCK；
- 日期按交易所 UTC 0 点重置。

### 11.2 冷却期触发与解除

- **触发**：每次平仓亏损（`actual_R < 0`）即进入冷却期，时长为 `cooldown_minutes_after_loss`（默认 30 分钟）；
- **期间**：冷却期内 RiskEngine 触发规则 8 BLOCK，禁止新开仓（允许平仓/减仓）；
- **解除**：冷却期到期后自动解除，无需手动操作；
- **连亏叠加**：若 `consecutive_losses >= max_consecutive_losses`（默认 2），规则 7 BLOCK 优先于冷却期规则 8，需连亏计数重置后才能恢复。

### 11.3 连亏计数

- 每次平仓亏损（`actual_R < 0`）`consecutive_losses += 1`；
- 每次平仓盈利（`actual_R > 0`）`consecutive_losses = 0`；
- 保本出场（`actual_R == 0`）不改变计数；
- 达到 `max_consecutive_losses` 即触发规则 7 BLOCK；
- 重置方式：用户在 Risk Center 手动重置，或等待冷却期结束后由系统提示重置。
