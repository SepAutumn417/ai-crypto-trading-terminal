# ADR-0005：前端实时状态采用 WebSocket 推送

## 状态

Accepted（2026-07-07）

## 背景

系统前端需要实时获取以下数据：

- **行情**：tick 价格、K线更新、订单簿快照（高频，单标的峰值 100 ticks/s）；
- **系统状态**：Kill Switch 状态、execution_enabled、连接状态（低频，但需即时推送）；
- **订单更新**：订单状态机变化、部分成交、止盈止损设置结果（事件驱动）；
- **持仓更新**：持仓变化、未实现盈亏（中频）。

候选推送机制：WebSocket、REST 轮询、Server-Sent Events（SSE）。

轮询的问题：

- tick 级行情轮询无法满足 ≤ 200ms 推送延迟目标（见 `PRD.md §8.5`）；
- 多频道轮询产生大量无效请求，服务器与客户端负载高；
- 订单状态变化若靠轮询，用户感知延迟可达数秒，影响 L4 确认体验。

SSE 的问题：

- 单向通信，前端无法通过同一连接发送订阅/取消订阅指令；
- 浏览器对 SSE 并发连接数有限制（同源 6 个）；
- 不支持二进制帧，订单簿快照序列化开销大。

## 决策

前端实时状态采用 **WebSocket 推送**，定义 6 个频道（见 `WEBSOCKET_API.md`）：

1. `market.ticker` — tick 价格；
2. `market.kline` — K线更新；
3. `market.orderbook` — 订单簿快照；
4. `system.status` — Kill Switch / execution_enabled / 连接状态；
5. `orders.updates` — 订单状态机变化；
6. `positions.updates` — 持仓变化。

## 后果

**正面**：

- 双向通信：前端可通过同一连接订阅/取消订阅频道；
- tick 级行情可满足 ≤ 200ms 推送延迟目标；
- 事件驱动的订单/持仓更新，用户感知即时；
- 单连接复用多频道，连接数可控（≤ 4，见 `PRD.md §8.6`）。

**负面**：

- 连接管理复杂：需处理心跳、重连、seq gap 检测（见 `WEBSOCKET_API.md §6-§8`）；
- 服务端需维护连接状态与订阅表；
- WebSocket 鉴权需单独设计（见 `WEBSOCKET_API.md §3`，token via query param）；
- 断线期间的事件需 REST 全量同步补齐（seq gap 处理）。

**强制约束**：

- 每条推送消息带 `seq` 单调递增字段，客户端检测 gap 后触发 REST 同步；
- 心跳：服务端每 20s 发 `ping`，客户端 30s 无 `pong` 则断开重连；
- 重连采用指数退避，最大间隔 30s；
- 订单/持仓频道断线期间禁止用户确认下单（见 `EXECUTION_SAFETY.md §2.3`）。

## 备选方案

| 方案 | 拒绝原因 |
|---|---|
| **REST 轮询** | tick 级行情无法满足延迟目标；无效请求多；订单状态变化感知慢 |
| **Server-Sent Events（SSE）** | 单向通信，无法同连接订阅管理；浏览器并发连接限制；不支持二进制 |
| **WebSocket + 轮询混合（行情轮询，订单 WS）** | 行情轮询延迟与负载均不达标，混合增加客户端复杂度 |
| **gRPC streaming** | 浏览器原生不支持，需 gRPC-Web 代理，部署复杂度高 |

## 关联

- `WEBSOCKET_API.md`：6 频道定义、心跳、重连、seq gap 处理；
- `EXECUTION_SAFETY.md §2.3`：WebSocket 断开禁止新单；
- `PRD.md §8.5 / §8.6`：推送延迟与并发连接目标；
- `ERROR_CODES.md §3.8`：WebSocket 错误码。
