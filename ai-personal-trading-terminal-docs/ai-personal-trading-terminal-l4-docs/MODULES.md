# 模块拆分文档

## 1. 模块总览

```text
apps/
  web/
  api/

packages/
  market-data/
  market-structure/
  auto-plan-engine/
  position-sizing-engine/
  risk-engine/
  ai-evaluation-agent/
  decision-gate/
  execution-engine/
  exchange-adapters/
  journal/
  review/
  config-versioning/
  event-log/
  shared/
```

---

## 2. apps/web

### 职责

- 提供个人交易终端Web界面；
- 展示行情、结构、机会、风控、AI评估；
- 处理用户确认执行；
- 展示日志和复盘。

### 主要页面

- Dashboard；
- Opportunity Radar；
- Chart Workspace；
- Trade Plan Center；
- Order Preview；
- Execution Monitor；
- Risk Center；
- Journal；
- Review；
- Settings。

---

## 3. apps/api

### 职责

- 对外提供REST/WebSocket API；
- 聚合各模块能力；
- 做权限检查；
- 写事件日志；
- 返回统一格式。

---

## 4. market-data

### 输入

- 交易所REST K线；
- 交易所WebSocket行情；
- 自选标的配置。

### 输出

- candles；
- market ticks；
- market events。

### 核心函数

- `syncCandles(symbol, timeframe)`；
- `subscribeTicker(symbol)`；
- `subscribeKline(symbol, timeframe)`；
- `publishMarketEvent(event)`。

---

## 5. market-structure

### 输入

- candles；
- timeframe；
- symbol。

### 输出

- trendDirection；
- marketState；
- swingHighs；
- swingLows；
- supportZones；
- resistanceZones；
- bosEvents；
- chochEvents；
- noTradeZones。

### 核心函数

- `detectSwings(candles, n)`；
- `detectTrend(swings)`；
- `detectRange(candles, swings)`；
- `detectBosChoch(swings, closes)`；
- `buildStructureSnapshot(symbol, timeframe)`。

---

## 6. auto-plan-engine

### 职责

根据结构快照生成候选交易计划。

### 输入

- structure snapshot；
- price；
- risk config；
- symbol rules。

### 输出

- candidate plans。

### 支持setupType

- `TREND_PULLBACK_LONG`；
- `TREND_PULLBACK_SHORT`；
- `RANGE_SUPPORT_BOUNCE`；
- `RANGE_RESISTANCE_REJECT`；
- `BREAKOUT_RETEST_LONG`；
- `BREAKDOWN_RETEST_SHORT`；
- `FALSE_BREAK_REVERSAL`。

---

## 7. position-sizing-engine

### 职责

自动以损定仓。

### 输入

- equity；
- riskPercent；
- entryPrice；
- stopLossPrice；
- leverage；
- symbol precision；
- feeRate。

### 输出

- riskAmount；
- stopDistancePercent；
- notionalValue；
- rawSize；
- roundedSize；
- requiredMargin；
- estimatedFee；
- estimatedLossAtStop；
- riskRewardRatio。

---

## 8. risk-engine

### 职责

硬风控检查。

### 输出

```json
{
  "status": "ALLOW | WARN | REDUCE_RISK | BLOCK",
  "maxAllowedRiskPercent": 1.5,
  "reasons": [],
  "warnings": [],
  "configVersion": "risk-v1"
}
```

---

## 9. ai-evaluation-agent

### 职责

解释结构、计划和风险。

### 注意

AI不得返回可绕过风控的结论。

---

## 10. decision-gate

### 职责

最终确认计划是否可以进入订单预览。

输入：

- plan；
- risk result；
- AI evaluation；
- system mode；
- execution enabled；
- user settings。

输出：

- `ALLOW_CONFIRM`；
- `WAIT`；
- `REDUCE_RISK`；
- `BLOCK`；
- `EXPIRED`。

---

## 11. execution-engine

### 职责

处理L4确认执行。

能力：

- build order intent；
- dry run；
- submit order；
- place TP/SL；
- cancel order；
- reconcile state；
- write execution logs。

---

## 12. exchange-adapters

### 职责

屏蔽交易所API差异。

第一实现：

- `BitgetAdapter`。

统一接口：

```ts
interface ExchangeAdapter {
  getAccountEquity(): Promise<AccountEquity>
  getPositions(): Promise<Position[]>
  placeOrder(input: ExchangeOrderInput): Promise<ExchangeOrderResult>
  cancelOrder(input: CancelOrderInput): Promise<CancelOrderResult>
  placeTpSl(input: TpSlInput): Promise<TpSlResult>
  getSymbolRules(symbol: string): Promise<SymbolRules>
}
```

---

## 13. journal

### 职责

记录计划、执行和结果。

### 输出

- trade_journal；
- execution_logs；
- review_items。

---

## 14. config-versioning

### 职责

管理风控、策略、用户配置版本。

---

## 15. event-log

### 职责

记录所有系统事件和审计事件。
