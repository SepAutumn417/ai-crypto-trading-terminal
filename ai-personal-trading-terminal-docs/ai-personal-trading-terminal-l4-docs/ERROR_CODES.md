# 错误码总表

> 本文档是错误码的**唯一事实源**。`API.md §14.5` 与各模块文档中的错误码引用本文件，不在他处重复定义。

## 1. 命名规范

### 1.1 命名规则

- 全大写 + 下划线分隔（`UPPER_SNAKE_CASE`）；
- 按模块加前缀，前缀与模块名对应；
- 名称表达"发生了什么"，不表达"谁导致"。

### 1.2 模块前缀

| 前缀 | 模块 | 示例 |
|---|---|---|
| （无前缀） | 通用 | `INVALID_INPUT`、`UNAUTHORIZED` |
| `RISK_` | 风控 | `RISK_BLOCKED`、`RISK_DAILY_LOSS_LIMIT_REACHED` |
| `CONFIG_` | 配置版本 | `CONFIG_NOT_FOUND`、`CONFIG_DUPLICATE_LABEL` |
| `PLAN_` | 交易计划 | `PLAN_NOT_FOUND`、`PLAN_EXPIRED` |
| `JOURNAL_` | 交易日志 | `JOURNAL_NOT_FOUND` |
| `ORDER_` | 订单执行 | `ORDER_NOT_CANCELLABLE`、`ORDER_CLIENT_OID_MISMATCH` |
| `EXCHANGE_` | 交易所适配器 | `EXCHANGE_NOT_CONNECTED`、`EXCHANGE_API_ERROR` |
| `AUTH_` | 鉴权 | `AUTH_FAILED`、`AUTH_SECOND_CONFIRMATION_REQUIRED` |
| `WS_` | WebSocket | `WS_SUBSCRIBE_FAILED`、`WS_AUTH_FAILED` |

> 历史代码 `KILL_SWITCH_ACTIVE`、`DUPLICATE_LABEL`、`ACTIVATE_CONFLICT` 等未严格按前缀命名，保留兼容，新增码必须按前缀规范。

---

## 2. HTTP 状态码映射规则

| HTTP | 含义 | 使用场景 |
|---|---|---|
| `400` | Bad Request | 请求体格式错误（非 JSON、字段类型错误） |
| `401` | Unauthorized | 未登录 / token 失效 |
| `403` | Forbidden | 已登录但无权限（如缺少二次确认） |
| `404` | Not Found | 资源不存在 |
| `409` | Conflict | 状态冲突（如计划状态不允许操作、label 重复、并发激活冲突） |
| `422` | Unprocessable Entity | 入参校验失败（语义错误，如杠杆超限、配置类型非法） |
| `423` | Locked | 资源被锁定（Kill Switch 激活中，禁止交易类操作） |
| `429` | Too Many Requests | 限流 |
| `500` | Internal Server Error | 服务端未预期错误 |
| `503` | Service Unavailable | 依赖不可用（交易所未连接、数据库不可用） |

### 2.1 映射原则

- 同一错误码固定映射到同一 HTTP 状态码，不随端点变化；
- `422` 专用于校验失败（ValidationError），不用于业务冲突；
- `409` 专用于状态/并发冲突；
- `423` 专用于 Kill Switch 激活导致的交易类操作锁定；
- `503` 专用于外部依赖不可用，服务端自身故障用 `500`。

### 2.2 幂等冲突处理

- 幂等 key 与请求体不匹配 → `422 IDEMPOTENCY_KEY_MISMATCH`（见 `API.md §14.3`）；
- 重复 `clientOid` → `409 ORDER_ALREADY_SUBMITTED`，返回首次结果引用。

---

## 3. 错误码总表

### 3.1 通用

| code | HTTP | 说明 |
|---|---|---|
| `INVALID_INPUT` | 422 | 入参校验失败（详见 §5 ValidationError） |
| `UNAUTHORIZED` | 401 | 未鉴权 / token 缺失或失效 |
| `FORBIDDEN` | 403 | 已登录但无权限（如缺少二次确认、IP 不在白名单） |
| `RATE_LIMITED` | 429 | 限流，响应带 `Retry-After` Header |
| `IDEMPOTENCY_KEY_MISMATCH` | 422 | 幂等 key 与请求体 hash 不匹配 |
| `EMPTY_DATA` | 422 | 请求体为空或缺少必填字段 |
| `INTERNAL_ERROR` | 500 | 服务端未预期错误 |
| `SERVICE_UNAVAILABLE` | 503 | 依赖不可用（非交易所场景） |

### 3.2 风控（RISK_ / KILL_SWITCH_*）

| code | HTTP | 说明 |
|---|---|---|
| `RISK_BLOCKED` | 422 | 风控拦截（BLOCK，含多条原因见 `blockReasons`） |
| `KILL_SWITCH_ACTIVE` | 423 | Kill Switch 激活中（`kill_switch=true`），禁止交易类操作 |
| `RISK_DAILY_LOSS_LIMIT_REACHED` | 422 | 当日亏损达到限制（`daily_loss_limit_r`） |
| `RISK_CONSECUTIVE_LOSS_LIMIT_REACHED` | 422 | 连续亏损达到限制（`max_consecutive_losses`） |
| `RISK_COOLDOWN_ACTIVE` | 422 | 冷却期未结束 |
| `RISK_LEVERAGE_EXCEEDED` | 422 | 杠杆超过配置上限 |
| `RISK_RR_TOO_LOW` | 422 | 盈亏比低于最低阈值 |
| `RISK_NO_STOP_LOSS` | 422 | 未设置止损 |
| `RISK_NOTIONAL_EQUITY_RATIO_EXCEEDED` | 422 | 名义价值 / 账户权益超过上限（`max_notional_equity_ratio`） |

> 风控拦截统一返回 `RISK_BLOCKED`，具体原因在 `details.blockReasons` 数组中列出；上表其余码为前端可单独识别的细分场景，可选择使用。Kill Switch 拦截单独使用 `KILL_SWITCH_ACTIVE` + HTTP 423，不与 `RISK_BLOCKED` 混用。

### 3.3 配置（CONFIG_）

| code | HTTP | 说明 |
|---|---|---|
| `CONFIG_NOT_FOUND` | 404 | 配置不存在（按 id 查询） |
| `CONFIG_VERSION_NOT_FOUND` | 404 | 配置版本不存在（按 type + version 查询） |
| `CONFIG_DUPLICATE_LABEL` | 409 | 配置版本 label 重复（`UNIQUE(config_type, version_label)`） |
| `CONFIG_INVALID_TYPE` | 422 | 配置类型非法（非 risk/strategy/execution/ai/user_trading/symbol 之一） |
| `CONFIG_ACTIVATE_CONFLICT` | 409 | 激活冲突（并发激活，部分唯一索引 `WHERE is_active=true` 冲突；并发控制与幂等处理见 `CONFIG_VERSIONING.md §6.1`） |

### 3.4 计划（PLAN_）

| code | HTTP | 说明 |
|---|---|---|
| `PLAN_NOT_FOUND` | 404 | 交易计划不存在 |
| `PLAN_STATUS_ERROR` | 409 | 计划状态不允许该操作（如已成交计划再次确认） |
| `PLAN_EXPIRED` | 409 | 计划已过期 |

### 3.5 执行（ORDER_ / EXCHANGE_）

| code | HTTP | 说明 |
|---|---|---|
| `ORDER_NOT_CANCELLABLE` | 409 | 订单不可撤（已进入终态：已成交/已撤/已拒绝） |
| `ORDER_ALREADY_SUBMITTED` | 409 | 订单已提交（`clientOid` 重复），返回首次结果引用 |
| `EXCHANGE_NOT_CONNECTED` | 503 | 交易所未连接（适配器未初始化或连接断开） |
| `EXCHANGE_API_ERROR` | 502 | 交易所 API 返回错误（非权限类，如限流、超时、5xx） |
| `EXCHANGE_SET_LEVERAGE_FAILED` | 502 | 设置杠杆失败 |
| `EXCHANGE_SET_MARGIN_MODE_FAILED` | 502 | 设置保证金模式失败 |
| `EXCHANGE_TP_SL_FAILED` | 502 | 止盈止损设置失败（触发 Kill Switch，见 `KILL_SWITCH.md §4`） |
| `ORDER_CLIENT_OID_MISMATCH` | 422 | 请求 `clientOid` 与 `order_intents.client_oid` 不一致 |

### 3.6 日志（JOURNAL_）

| code | HTTP | 说明 |
|---|---|---|
| `JOURNAL_NOT_FOUND` | 404 | 交易日志不存在 |
| `JOURNAL_STATUS_ERROR` | 409 | 日志状态不允许该操作（如已锁定的日志尝试修改） |

### 3.7 鉴权（AUTH_）

| code | HTTP | 说明 |
|---|---|---|
| `AUTH_FAILED` | 401 | 用户名/口令错误 |
| `AUTH_SESSION_EXPIRED` | 401 | Session 过期 / 被踢下线 / token 失效 |
| `AUTH_SECOND_CONFIRMATION_REQUIRED` | 403 | 高危操作需要二次确认（返回 `challengeId`） |
| `AUTH_SECOND_CONFIRMATION_FAILED` | 403 | 二次确认失败（口令错误 / TOTP 错误 / challenge 过期） |
| `AUTH_LOGIN_LOCKED` | 429 | 登录失败次数超限，临时锁定 |

### 3.8 WebSocket（WS_）

| code | HTTP / 关闭码 | 说明 |
|---|---|---|
| `WS_SUBSCRIBE_FAILED` | 错误帧 | 订阅失败（频道名非法 / 超过订阅上限） |
| `WS_AUTH_FAILED` | 关闭 4401 | token 缺失 / 过期 / 无效 |
| `WS_RATE_LIMITED` | 关闭 4429 | 推送或订阅频次超限 |
| `WS_SEQUENCE_GAP` | 错误帧 | 服务端检测到 seq gap，客户端应 REST 全量同步 |

> WebSocket 错误不通过 HTTP 响应返回，见 `WEBSOCKET_API.md §11`。

---

## 4. 错误响应体格式

所有错误响应遵循统一 envelope（见 `API.md §1`）：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "RISK_BLOCKED",
    "message": "当前计划未通过风控检查",
    "details": {
      "blockReasons": ["NO_STOP_LOSS", "RR_TOO_LOW"],
      "riskResultId": "uuid"
    }
  },
  "requestId": "01HXXXXXXXXXXXXXXX"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `success` | boolean | 固定 `false` |
| `data` | null | 固定 `null` |
| `error.code` | string | 错误码（见 §3） |
| `error.message` | string | 面向用户的可读消息（中文） |
| `error.details` | object | 错误详情，结构随 code 变化；校验类错误见 §5 |
| `requestId` | string | 请求追踪 ID（UUID 或 ULID），与响应 Header `X-Request-Id` 一致 |

### 4.1 details 常见结构

- 风控类：`{"blockReasons": [...], "riskResultId": "uuid"}`；
- 幂等类：`{"idempotencyKey": "...", "expectedHash": "...", "actualHash": "..."}`；
- 二次确认：`{"challengeId": "uuid", "expiresAt": "ISO8601"}`；
- Kill Switch：`{"killSwitch": true, "trigger": "auto", "autoCondition": "tp_sl_failed"}`。

---

## 5. ValidationError 详情格式

`INVALID_INPUT`（HTTP 422）的 `details` 使用标准化的 `errors` 数组，兼容 Pydantic v2 / FastAPI 校验输出：

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_INPUT",
    "message": "入参校验失败",
    "details": {
      "errors": [
        {
          "loc": ["body", "leverage"],
          "msg": "leverage must be > 0",
          "type": "value_error",
          "input": 0
        },
        {
          "loc": ["body", "password"],
          "msg": "field required",
          "type": "missing",
          "input": null
        }
      ]
    }
  },
  "requestId": "01HXXXXXXXXXXXXXXX"
}
```

### 5.1 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `loc` | array | 错误位置路径（`[body, <field>]` / `[query, <param>]` / `[path, <param>]`） |
| `msg` | string | 错误消息 |
| `type` | string | 错误类型（Pydantic 的错误类型枚举，如 `value_error` / `missing` / `type_error`） |
| `input` | any | 用户传入的值（**脱敏后**，见 §5.2） |

### 5.2 input 字段脱敏

`input` 字段对敏感字段名做黑名单过滤，命中时值替换为 `"[REDACTED]"`：

| 字段名（大小写不敏感，含子串匹配） | 脱敏动作 |
|---|---|
| `password` / `passwd` / `pwd` | 替换为 `"[REDACTED]"` |
| `secret` | 替换为 `"[REDACTED]"` |
| `token` / `apikey` / `api_key` / `access_token` / `refresh_token` | 替换为 `"[REDACTED]"` |
| `passphrase` | 替换为 `"[REDACTED]"` |
| `totp` / `otp` | 替换为 `"[REDACTED]"` |
| `master_key` | 替换为 `"[REDACTED]"` |

### 5.3 脱敏示例

用户提交 `{ "password": "123", "leverage": 0 }`，校验失败时返回：

```json
{
  "errors": [
    {"loc": ["body", "password"], "msg": "password too short", "type": "value_error", "input": "[REDACTED]"},
    {"loc": ["body", "leverage"], "msg": "leverage must be > 0", "type": "value_error", "input": 0}
  ]
}
```

### 5.4 实现约束

- 脱敏在序列化 `details` 之前完成，原值不得进入日志或 `system_events.payload`；
- 脱敏黑名单通过配置项 `SENSITIVE_FIELD_NAMES` 扩展（默认值见 §5.2）；
- 嵌套对象中的敏感字段同样脱敏（递归处理）。
