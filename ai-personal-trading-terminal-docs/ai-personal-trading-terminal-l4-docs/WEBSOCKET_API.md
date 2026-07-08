# WebSocket API 设计

## 1. 目标

WebSocket 通道用于服务端主动推送，覆盖三类场景：

- **行情推送**：实时 ticker、增量 K 线、订单簿增量；
- **账户更新**：订单状态变化、持仓变化；
- **系统状态广播**：Kill Switch / execution_enabled 变化、交易所连接状态变化。

REST API 仍是权威数据源，WebSocket 仅做低延迟推送。客户端在 seq gap 或重连后必须通过 REST 全量同步。

---

## 2. 连接

### 2.1 端点

```text
ws://localhost:8000/ws
```

- 生产环境经 Nginx 反代：`wss://<domain>/ws`（见 `AUTH.md §7.3`）；
- 后端绑定 `127.0.0.1`，不监听公网。

### 2.2 鉴权 token 传递

连接时必须携带鉴权 token（二选一）：

| 方式 | 示例 | 适用 |
|---|---|---|
| Query param | `ws://localhost:8000/ws?token=<jwt>` | 浏览器原生 WebSocket（无法设 Header） |
| Header | `Authorization: Bearer <jwt>` | 程序化客户端 |

- public 频道（`market.*`）连接时可不带 token，但仍受 IP 白名单限制（见 `AUTH.md §7`）；
- private 频道（`orders.*` / `positions.*` / `system.*`）连接时必须带有效 token，否则服务端立即关闭连接（code=4401）。

### 2.3 握手响应

连接建立后服务端先发：

```json
{
  "channel": "system.status",
  "type": "snapshot",
  "data": {
    "killSwitch": true,
    "executionEnabled": false,
    "exchangeConnected": true,
    "websocketConnected": true,
    "databaseHealthy": true
  },
  "timestamp": "2026-07-07T10:00:00Z",
  "seq": 0
}
```

> Kill Switch 极性约定：`killSwitch = true` 表示已激活（熔断态），见 `KILL_SWITCH.md §2`。

---

## 3. 频道定义

| 频道 | 类型 | 说明 | 引入版本 |
|---|---|---|---|
| `market.ticker.{symbol}` | public | 实时 ticker（最新价、24h 涨跌、量） | v0.2 |
| `market.kline.{symbol}.{timeframe}` | public | 增量 K 线（未收盘更新 + 收盘推送） | v0.2 |
| `market.orderbook.{symbol}` | public | 订单簿增量（depth 前 N 档） | v0.2 |
| `system.status` | private | Kill Switch / execution_enabled / 连接状态变化广播 | v0.8 |
| `orders.updates` | private | 订单状态变化推送（含 client_oid） | v0.7 |
| `positions.updates` | private | 持仓变化推送 | v0.7 |

### 3.1 频道命名规范

- 小写 + 点分层级；
- `{symbol}` 大写（如 `BTCUSDT`）；
- `{timeframe}` 取 `1m / 5m / 15m / 1h / 4h / 1d`；
- 通配：`market.ticker.*` 订阅全部 symbol（受服务端限流约束）。

---

## 4. 消息格式

所有推送消息统一结构：

```json
{
  "channel": "market.ticker.BTCUSDT",
  "type": "snapshot",
  "data": {},
  "timestamp": "2026-07-07T10:00:00.123Z",
  "seq": 42
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `channel` | string | 频道名（含具体 symbol/timeframe） |
| `type` | enum | `snapshot`（全量快照）/ `update`（增量更新） |
| `data` | object | 频道特定数据 |
| `timestamp` | ISO8601 | 服务端发送时间（毫秒精度） |
| `seq` | integer | 频道内递增序列号，从 1 开始 |

### 4.1 各频道 data 字段

#### market.ticker

```json
{
  "symbol": "BTCUSDT",
  "lastPrice": "62400.5",
  "change24h": "1.23",
  "high24h": "63100",
  "low24h": "61800",
  "volume24h": "1234.56"
}
```

#### market.kline

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "openTime": 1731000000000,
  "open": "62300",
  "high": "62500",
  "low": "62250",
  "close": "62400",
  "volume": "12.3",
  "closed": false
}
```

> `closed=true` 表示该 K 线已收盘，客户端应固化；`closed=false` 表示未收盘，继续覆盖。

#### market.orderbook

```json
{
  "symbol": "BTCUSDT",
  "bids": [["62400", "0.5"], ["62399", "1.2"]],
  "asks": [["62401", "0.3"], ["62402", "0.8"]]
}
```

- `snapshot` 推送前 N 档全量；
- `update` 推送变化的档位（价格为 key，数量为 0 表示删除该档）。

#### system.status

```json
{
  "killSwitch": true,
  "executionEnabled": false,
  "exchangeConnected": true,
  "websocketConnected": true,
  "databaseHealthy": true,
  "latestEventType": "KILL_SWITCH_TOGGLED"
}
```

#### orders.updates

```json
{
  "orderId": "uuid",
  "clientOid": "apt-uuid",
  "status": "FILLED",
  "filledSize": "0.0065",
  "avgPrice": "62400",
  "exchangeOrderId": "bg-xxx"
}
```

> `clientOid` 必须与 `order_intents.client_oid` 一致（见 `API.md §8.3`）。

#### positions.updates

```json
{
  "positionId": "uuid",
  "symbol": "BTCUSDT",
  "side": "LONG",
  "size": "0.0065",
  "entryPrice": "62400",
  "markPrice": "62500",
  "unrealizedPnl": "0.65",
  "leverage": 10
}
```

---

## 5. 订阅 / 取消订阅

### 5.1 订阅

```json
{
  "op": "subscribe",
  "channels": ["market.ticker.BTCUSDT", "market.kline.BTCUSDT.15m"]
}
```

响应：

```json
{
  "op": "subscribe",
  "result": "ok",
  "channels": ["market.ticker.BTCUSDT", "market.kline.BTCUSDT.15m"]
}
```

### 5.2 取消订阅

```json
{
  "op": "unsubscribe",
  "channels": ["market.ticker.BTCUSDT"]
}
```

### 5.3 约束

- 单连接订阅频道数上限 50（防资源滥用）；
- 单 symbol 的 `market.*` 频道自动聚合限流；
- 订阅 private 频道时若 token 已失效，返回 `WS_AUTH_FAILED` 并关闭连接。

---

## 6. 鉴权

### 6.1 频道分级

| 频道前缀 | 类型 | 鉴权 |
|---|---|---|
| `market.*` | public | 无需 token，受 IP 白名单限制 |
| `system.*` / `orders.*` / `positions.*` | private | 必须有效 token |

### 6.2 鉴权失败处理

- 连接时 token 缺失/过期 → 服务端发送 `WS_AUTH_FAILED` 错误帧后关闭（code=4401）；
- 订阅 private 频道时 token 失效 → 返回错误帧，该频道不订阅；
- token 过期后已订阅的 private 频道停止推送，发 `WS_AUTH_FAILED`。

### 6.3 token 续期

WebSocket 连接不自动续期 token。客户端应在 token 即将过期前用新 token 重连，或通过 REST `/api/auth/refresh` 获取新 token 后断开重连。

---

## 7. 心跳

### 7.1 服务端 ping

- 服务端每 **20 秒**发送 `ping`（文本帧 `"ping"`）；
- 客户端必须在 **60 秒**内回 `pong`（文本帧 `"pong"`）；
- 超时未收到 `pong`，服务端主动关闭连接（code=4408）。

### 7.2 客户端 ping

- 客户端可主动发送 `ping`，服务端立即回 `pong`；
- 客户端 30 秒未收到任何帧（含 ping）应判定连接异常并重连。

### 7.3 心跳与 seq

心跳帧不携带 `seq`，不计入频道序列号。

---

## 8. 重连

### 8.1 客户端重连策略

- 指数退避：1s → 2s → 4s → 8s → 16s → 30s（上限）；
- 重连成功后：
  1. 重新发送鉴权 token；
  2. 重新订阅之前的频道；
  3. 对每个频道记录的 `last_seq` 与服务端首帧 `seq` 比较，若 gap 则触发 REST 全量同步。

### 8.2 服务端 snapshot 推送

服务端在以下场景主动推送 `snapshot`：

- 客户端首次订阅某频道；
- 服务端检测到 seq gap（如服务端重启、客户端断线期间有更新）；
- 行情快照周期性刷新（默认 60 秒一次，防增量累积误差）。

### 8.3 服务端重启

服务端重启后所有 `seq` 从 1 重新开始。客户端检测到 `seq` 回退（新 seq < last_seq）时，应丢弃旧状态并按 `snapshot` 重建。

---

## 9. 序列号

### 9.1 序列号规则

- 每个频道独立维护递增 `seq`，从 1 开始；
- `snapshot` 和 `update` 共享同一 `seq` 序列；
- `seq` 单调递增，不回退（服务端重启除外，见 §8.3）。

### 9.2 gap 检测

客户端对每个频道记录 `last_seq`：

- 收到的 `seq == last_seq + 1` → 正常；
- 收到的 `seq > last_seq + 1` → gap，调用 REST 全量同步，并用本帧 `seq` 重置 `last_seq`；
- 收到的 `seq <= last_seq` → 丢弃（重复帧），但记录日志。

### 9.3 全量同步端点

| 频道 | REST 全量同步端点 |
|---|---|
| `market.ticker.{symbol}` | `GET /api/market/ticker?symbol=` |
| `market.kline.{symbol}.{tf}` | `GET /api/market/candles?symbol=&timeframe=&limit=` |
| `market.orderbook.{symbol}` | `GET /api/market/orderbook?symbol=` |
| `orders.updates` | `GET /api/orders?status=active` |
| `positions.updates` | `GET /api/positions` |
| `system.status` | `GET /api/system/status` |

---

## 10. 版本引入

| 版本 | WebSocket 能力 |
|---|---|
| v0.1 | 不实现（无行情接入） |
| **v0.2** | **market 频道**（ticker / kline / orderbook），public 鉴权豁免 |
| v0.5 | 行情频道稳定性加固、限流 |
| **v0.7** | **private 频道**（orders.updates / positions.updates），token 鉴权 |
| **v0.8** | **system.status 广播**（Kill Switch / execution_enabled 变化） |
| v1.0 | 全量稳定性验收、重连/snapshot 全链路测试 |

---

## 11. 错误码

WebSocket 专用错误码（完整错误码总表见 `ERROR_CODES.md`）：

| code | 关闭码 / 帧类型 | 说明 | 处理建议 |
|---|---|---|---|
| `WS_SUBSCRIBE_FAILED` | 错误帧 | 订阅失败（频道名非法/超限） | 检查频道名、减少订阅数 |
| `WS_AUTH_FAILED` | 关闭 4401 / 错误帧 | token 缺失/过期/无效 | 重新登录获取 token 后重连 |
| `WS_RATE_LIMITED` | 关闭 4429 | 推送或订阅频次超限 | 降低订阅数，退避重连 |
| `WS_SEQUENCE_GAP` | 错误帧（服务端检测） | 服务端检测到客户端 seq gap | 客户端应触发 REST 全量同步 |

### 11.1 错误帧格式

```json
{
  "op": "error",
  "error": {
    "code": "WS_SUBSCRIBE_FAILED",
    "message": "频道名非法: market.ticker.",
    "details": {"channel": "market.ticker."}
  },
  "timestamp": "2026-07-07T10:00:00Z"
}
```

### 11.2 关闭码约定

| 关闭码 | 含义 |
|---|---|
| 1000 | 正常关闭 |
| 4401 | 鉴权失败 |
| 4408 | 心跳超时 |
| 4429 | 限流 |
| 4500 | 服务端内部错误 |
