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
  "clientOid": "apt-uuid"
}
```

返回：执行结果。

> 字段统一为 `clientOid`（与 Bitget API 字段一致），早期文档中的 `clientNonce` 已废弃。`clientOid` 必须与 `order_intents.client_oid` 一致，用于交易所层幂等去重。

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

---

## 14. API 通用约定

### 14.1 API 版本化

- 所有端点加 `/api/v1/` 前缀（v0.1 ~ v0.2 期间可兼容 `/api/` 旧前缀，v0.3 起强制 `/api/v1/`）；
- 客户端可通过 Header `X-API-Version: 1` 显式声明版本；
- Deprecation 政策：旧版本端点废弃后保留 2 个版本周期，响应 Header `Sunset: <date>` 标记移除时间；
- Breaking change 需升主版本号（`/api/v2/`）。

### 14.2 分页规范

列表端点统一使用游标分页：

```
GET /api/v1/trade-plans?limit=20&cursor=<encoded>&sort=-created_at
```

- `limit`：每页条数，默认 20，上限 100；
- `cursor`：base64 编码的游标（含排序字段值 + id），首次请求不传；
- `sort`：排序字段，`-` 前缀表示降序，如 `-created_at`；
- 响应：

```json
{
  "success": true,
  "data": {
    "items": [...],
    "next_cursor": "<encoded-or-null>",
    "has_more": true
  }
}
```

适用于：`/api/orders`、`/api/journal`、`/api/auto-plans`、`/api/trade-plans`、`/api/configs`、`/api/system/events`。

### 14.3 幂等策略

| 端点类型 | 幂等策略 |
|---|---|
| 查询类（GET） | 天然幂等 |
| 状态切换类（kill-switch / execution-mode / activate） | 同值幂等：重复请求相同状态返回 200 + 当前态，不报错 |
| 创建类（trade-plans / configs / journal） | 客户端传 `Idempotency-Key` Header（UUID），同 key 重复请求返回首次结果 |
| 订单提交类（confirm） | 使用 `clientOid` 幂等去重，交易所层拒绝重复 `clientOid` |

`Idempotency-Key` 缓存 24 小时，key 与请求体 hash 须匹配，不匹配返回 `IDEMPOTENCY_KEY_MISMATCH` 422。

### 14.4 限流

| 端点 | 限流 |
|---|---|
| `POST /api/v1/execution/{id}/confirm` | 1 req / 10s |
| `POST /api/v1/system/kill-switch` | 1 req / 5s |
| `POST /api/v1/configs/{id}/activate` | 1 req / 5s |
| 其他写端点 | 10 req / s |
| 读端点 | 60 req / min |

超限返回 `429 Too Many Requests` + `Retry-After` Header。

### 14.5 错误码总表

> 完整错误码见 `ERROR_CODES.md`。此处列出常用码：

| code | HTTP | 说明 |
|---|---|---|
| `RISK_BLOCKED` | 422 | 风控拦截 |
| `CONFIG_NOT_FOUND` | 404 | 配置不存在 |
| `CONFIG_VERSION_NOT_FOUND` | 404 | 配置版本不存在 |
| `DUPLICATE_LABEL` | 409 | 配置版本 label 重复 |
| `ACTIVATE_CONFLICT` | 409 | 激活冲突（并发） |
| `PLAN_NOT_FOUND` | 404 | 计划不存在 |
| `PLAN_STATUS_ERROR` | 409 | 计划状态不允许操作 |
| `JOURNAL_NOT_FOUND` | 404 | 日志不存在 |
| `ORDER_NOT_CANCELLABLE` | 409 | 订单不可撤（终态） |
| `INVALID_CONFIG_TYPE` | 422 | 配置类型非法 |
| `INVALID_INPUT` | 422 | 入参校验失败 |
| `IDEMPOTENCY_KEY_MISMATCH` | 422 | 幂等 key 与请求体不匹配 |
| `KILL_SWITCH_ACTIVE` | 423 | Kill Switch 激活中，禁止操作 |
| `EXCHANGE_NOT_CONNECTED` | 503 | 交易所未连接 |
| `UNAUTHORIZED` | 401 | 未鉴权 |
| `FORBIDDEN` | 403 | 无权限 |
| `RATE_LIMITED` | 429 | 限流 |
