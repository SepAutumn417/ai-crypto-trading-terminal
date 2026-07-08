# L4执行系统设计

## 1. 目标

L4执行系统用于解决“系统已经完成计划和仓位计算后，用户仍需手动去交易平台输入订单参数”的低效问题。

系统目标：

1. 自动生成交易所订单参数；
2. 在用户确认后提交订单；
3. 自动同步订单和持仓状态；
4. 自动记录执行过程；
5. 在异常情况下进入安全模式。

---

## 2. 执行边界

### 2.1 允许

- 用户确认后下限价单；
- 用户确认后撤销未成交订单；
- 用户确认后提交止盈止损；
- 用户确认后关闭仓位；
- 系统同步成交和持仓。

### 2.2 不允许

- 系统无确认自动开仓；
- AI直接下单；
- 风控未通过仍下单；
- 无止损开仓；
- 自动加仓；
- 自动反手；
- 使用提现权限；
- 在Kill Switch关闭后开新单。

---

## 3. 执行流程

```text
Trade Plan
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
Build Exchange Payload
  ↓
Submit Order
  ↓
Sync Order State
  ↓
Place / Confirm TP SL
  ↓
Position Monitor
  ↓
Journal
```

---

## 4. 执行引擎职责

`execution-engine` 负责：

- 创建订单意图 `order_intent`；
- 生成交易所请求体；
- 做Dry Run；
- 检查幂等键；
- 提交订单；
- 解析交易所响应；
- 设置止盈止损；
- 监听订单状态；
- 记录执行日志；
- 处理错误。

---

## 5. 订单意图 Order Intent

订单意图是提交交易所之前的内部订单对象。

```json
{
  "intentId": "uuid",
  "planId": "uuid",
  "symbol": "BTCUSDT",
  "productType": "USDT-FUTURES",
  "marginMode": "isolated",
  "direction": "LONG",
  "orderType": "limit",
  "entryPrice": "62400",
  "stopLossPrice": "61900",
  "takeProfitPrices": ["63800", "64500"],
  "size": "0.0065",
  "leverage": 10,
  "clientOid": "apt-uuid",
  "riskConfigVersion": "risk-v1",
  "status": "DRAFT"
}
```

---

## 6. Dry Run

Dry Run 是L4前必须完成的安全阶段。

Dry Run 会：

- 生成完整订单参数；
- 生成交易所请求体；
- 校验精度；
- 校验风控；
- 写执行日志；
- 不调用真实下单接口。

Dry Run 通过后才能进入真实执行阶段。

---

## 7. 用户确认

真实订单提交前必须有用户确认。

订单预览必须显示：

- 交易对；
- 方向；
- 入场价；
- 止损价；
- 止盈价；
- 数量；
- 杠杆；
- 保证金模式；
- 最大计划亏损；
- 所需保证金；
- 预估手续费；
- 盈亏比；
- 风控结论；
- AI解释。

高风险情况下必须二次确认。

---

## 8. 幂等设计

每笔订单必须使用唯一 `clientOid`。

规则：

- 同一个 `clientOid` 不允许重复提交；
- 网络超时后先查询状态，不能直接重试创建；
- 请求体Hash必须记录；
- 重试必须带原 `clientOid`。

---

## 9. 错误处理

| 错误 | 处理 |
|---|---|
| 下单失败 | 标记FAILED，记录原因 |
| 网络超时 | 查询订单状态，禁止盲目重试 |
| 部分成交 | 进入PARTIALLY_FILLED，继续监听 |
| 止损设置失败 | 触发严重报警，禁止新单 |
| WebSocket断开 | 暂停新订单，进入只读轮询 |
| 数据库写入失败 | 禁止提交订单 |
| 风控状态变化 | 中止提交 |

---

## 10. Kill Switch

Kill Switch关闭后：

- 禁止新开仓；
- 禁止加仓；
- 允许撤单；
- 允许减仓/平仓；
- 禁止订单预览进入确认提交。

---

## 11. 推荐执行模式

> 版本号以 `DEVELOPMENT.md §3` 与 `MVP_ACCEPTANCE.md` 为准：v0.7 为只读实盘同步，v0.8 为小额 L4 确认执行，v1.0 为稳定 L4。

### v0.8 小额L4

- 仅限限价单；
- 仅限逐仓；
- 每单必须止损；
- 每单必须用户确认；
- 每单必须记录执行日志；
- 不支持自动加仓；
- 不支持自动反手。

### v1.0 稳定L4

- 支持限价单；
- 支持计划止盈止损；
- 支持撤单；
- 支持持仓监控；
- 支持平仓确认执行。
