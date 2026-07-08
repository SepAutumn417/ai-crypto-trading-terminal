# 交易所接入设计

## 1. 第一接入交易所

第一阶段接入：**Bitget USDT-M Futures**。

原因：

- 支持合约交易API；
- 支持下单、撤单、止盈止损；
- 支持私有WebSocket订单推送；
- 支持API Key权限配置；
- 适合个人终端进行只读同步与确认执行。

---

## 2. 接入原则

1. 先只读，后执行；
2. 先Dry Run，后真实下单；
3. 先限价单，后更多订单类型；
4. 先逐仓，后考虑其他保证金模式；
5. 不启用提现权限；
6. 使用IP白名单；
7. 所有请求记录审计。

---

## 3. API Key权限

### 3.1 只读Key

用途：

- 查询账户权益；
- 查询持仓；
- 查询订单；
- 查询成交历史。

### 3.2 交易Key

用途：

- 提交订单；
- 撤单；
- 设置止盈止损。

限制：

- 不开启提现；
- 不开启划转，除非未来明确需要；
- 绑定服务器IP；
- 独立加密存储；
- 可随时手动禁用。

Bitget公开资料中列出的API权限包含 Read-only、Trade、Withdraw 等范围，项目实现时必须遵守最小权限原则。

---

## 4. 交易接口能力

Bitget 合约下单接口支持常见订单参数，例如：

- `symbol`；
- `productType`；
- `marginMode`；
- `marginCoin`；
- `size`；
- `price`；
- `side`；
- `tradeSide`；
- `orderType`；
- `force`；
- `clientOid`；
- preset take-profit / stop-loss fields。

系统需要在适配器层处理这些交易所参数，业务层不能直接拼交易所请求。

---

## 5. 止盈止损

系统支持两种方式：

### 5.1 下单时预设TP/SL

开仓订单直接携带预设止盈止损字段。

优点：

- 快；
- 流程短。

风险：

- 需要验证不同订单类型和持仓模式是否兼容。

### 5.2 成交后设置TP/SL计划单

开仓成交后再调用止盈止损计划单接口。

优点：

- 状态更清晰；
- 便于单独处理失败。

风险：

- 成交到止损设置之间存在短暂裸露风险；
- 如果设置失败必须立即报警。

### 5.3 推荐

> 版本号以 `DEVELOPMENT.md §3` 为准：v0.7 为只读实盘同步，v0.8 为小额 L4 确认执行。

v0.8 小额L4阶段优先使用更容易验证的保守流程。

v1.0 可以支持两种方式，并通过配置选择。

---

## 6. WebSocket同步

私有订单频道用于监听：

- 下单；
- 成交；
- 撤单；
- 修改。

系统需要：

- 订阅订单频道；
- 维护本地订单状态；
- 定期REST对账；
- WebSocket断开时禁止新订单。

---

## 7. 精度规则

交易所适配器必须处理：

- 价格精度；
- 数量精度；
- 最小下单数量；
- 最小名义价值；
- 杠杆范围；
- 保证金模式；
- 方向字段映射；
- 持仓模式差异。

所有精度处理必须在 `exchange-adapters` 中完成。

---

## 8. 交易所适配器接口

```ts
interface ExchangeAdapter {
  getExchangeName(): string
  getServerTime(): Promise<number>
  getAccountEquity(): Promise<AccountEquity>
  getPositions(): Promise<Position[]>
  getOpenOrders(symbol?: string): Promise<Order[]>
  getSymbolRules(symbol: string): Promise<SymbolRules>
  placeOrder(input: ExchangeOrderInput): Promise<ExchangeOrderResult>
  cancelOrder(input: CancelOrderInput): Promise<CancelOrderResult>
  placeTpSl(input: TpSlInput): Promise<TpSlResult>
  subscribeOrders(handler: OrderEventHandler): Promise<void>
}
```

---

## 9. 参考资料

- Bitget Contract Place Order Documentation
- Bitget Contract TP/SL Plan Order Documentation
- Bitget Contract WebSocket Private Order Channel Documentation
- Bitget API Key Permission Guidance

这些文档在实现前必须重新核对最新版本，避免字段更新导致执行错误。
