# API设计初稿

## 1. 统一响应格式

```json
{
  "success": true,
  "data": {},
  "error": null,
  "requestId": "uuid"
}
```

错误格式：

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

---

## 2. Market APIs

### GET `/api/market/candles`

参数：

- exchange；
- symbol；
- timeframe；
- limit。

返回：K线数组。

### GET `/api/market/ticker`

返回当前价格信息。

---

## 3. Structure APIs

### POST `/api/structure/analyze`

请求：

```json
{
  "exchange": "bitget",
  "symbol": "BTCUSDT",
  "timeframes": ["15m", "1h", "4h"]
}
```

返回：结构快照。

---

## 4. Auto Plan APIs

### POST `/api/auto-plans/scan`

扫描自选标的，生成候选计划。

请求：

```json
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "timeframes": ["15m", "1h"],
  "mode": "training"
}
```

返回：候选计划列表。

### GET `/api/auto-plans`

查询候选计划。

### POST `/api/auto-plans/{id}/promote`

将候选计划提升为正式交易计划。

---

## 5. Trade Plan APIs

### POST `/api/trade-plans`

创建手动交易计划。

请求：

```json
{
  "exchange": "bitget",
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "entryPrice": 62400,
  "stopLossPrice": 61900,
  "takeProfitPrices": [63800, 64500],
  "leverage": 10,
  "riskPercent": 1
}
```

### POST `/api/trade-plans/{id}/check`

执行仓位计算、风控检查、AI评估和决策门。

返回：

- sizingResult；
- riskResult；
- aiEvaluation；
- decisionGateResult。

---

## 6. Risk APIs

### POST `/api/risk/calculate-position`

单独计算仓位。

### POST `/api/risk/check`

对计划做风控检查。

---

## 7. AI APIs

### POST `/api/ai/evaluate-plan`

对交易计划进行AI评估。

### POST `/api/ai/review-trade`

生成交易复盘。

---

## 8. Execution APIs

## 8.1 创建订单预览

### POST `/api/execution/order-preview`

请求：

```json
{
  "tradePlanId": "uuid"
}
```

返回：

```json
{
  "orderIntentId": "uuid",
  "preview": {
    "symbol": "BTCUSDT",
    "direction": "LONG",
    "orderType": "limit",
    "price": 62400,
    "size": "0.0065",
    "leverage": 10,
    "maxLoss": 15,
    "requiredMargin": 187.5,
    "stopLossPrice": 61900,
    "takeProfitPrices": [63800, 64500]
  },
  "requiresSecondConfirmation": true
}
```

## 8.2 Dry Run

### POST `/api/execution/{orderIntentId}/dry-run`

生成交易所请求体但不提交。

## 8.3 用户确认执行

### POST `/api/execution/{orderIntentId}/confirm`

请求：

```json
{
  "confirmationText": "CONFIRM",
  "clientNonce": "uuid"
}
```

返回：执行结果。

## 8.4 撤单

### POST `/api/execution/orders/{orderId}/cancel`

需要用户确认。

---

## 9. Order APIs

### GET `/api/orders`

查询订单列表。

### GET `/api/orders/{id}`

查询订单详情。

### GET `/api/orders/{id}/events`

查询订单状态事件。

---

## 10. Position APIs

### GET `/api/positions`

查询当前持仓。

### POST `/api/positions/{id}/close-preview`

生成平仓预览。

### POST `/api/positions/{id}/close-confirm`

确认平仓。

---

## 11. Journal APIs

### POST `/api/journal`

创建交易日志。

### GET `/api/journal`

查询交易日志。

### GET `/api/journal/stats`

交易统计。

---

## 12. Config APIs

### GET `/api/configs/active`

查询当前激活配置。

### POST `/api/configs`

创建配置版本。

### POST `/api/configs/{id}/activate`

激活配置版本。

---

## 13. System APIs

### GET `/api/system/status`

返回系统状态：

- executionEnabled；
- killSwitch；
- exchangeConnected；
- websocketConnected；
- databaseHealthy；
- latestEvent。

### POST `/api/system/kill-switch`

开启/关闭Kill Switch。
