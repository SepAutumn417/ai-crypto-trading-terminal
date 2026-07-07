# 数据库设计初稿

## 1. 技术选择

推荐数据库：PostgreSQL。

推荐配套：

- Redis：缓存、任务队列、实时状态；
- JSONB：存储结构快照、AI输出、交易所响应。

---

## 2. 表总览

| 表 | 作用 |
|---|---|
| `candles` | K线数据 |
| `market_structure_snapshots` | 市场结构快照 |
| `candidate_plans` | 自动候选交易计划 |
| `trade_plans` | 正式交易计划 |
| `position_sizing_results` | 仓位计算结果 |
| `risk_checks` | 风控检查结果 |
| `ai_evaluations` | AI评估结果 |
| `decision_gate_results` | 决策门结果 |
| `order_intents` | 内部订单意图 |
| `exchange_orders` | 交易所订单 |
| `order_state_events` | 订单状态事件 |
| `positions` | 持仓快照 |
| `trade_journal` | 交易日志 |
| `review_reports` | 复盘报告 |
| `config_versions` | 配置版本 |
| `system_events` | 系统事件 |
| `api_keys` | API Key元数据，不存明文 |
| `user_settings` | 用户设置 |

---

## 3. 核心表结构

## 3.1 candles

```sql
CREATE TABLE candles (
  id BIGSERIAL PRIMARY KEY,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(16) NOT NULL,
  open_time TIMESTAMPTZ NOT NULL,
  close_time TIMESTAMPTZ,
  open NUMERIC NOT NULL,
  high NUMERIC NOT NULL,
  low NUMERIC NOT NULL,
  close NUMERIC NOT NULL,
  volume NUMERIC,
  quote_volume NUMERIC,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(exchange, symbol, timeframe, open_time)
);
```

---

## 3.2 market_structure_snapshots

```sql
CREATE TABLE market_structure_snapshots (
  id UUID PRIMARY KEY,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(16) NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  market_state VARCHAR(32),
  trend_direction VARCHAR(32),
  support_zones JSONB,
  resistance_zones JSONB,
  swing_highs JSONB,
  swing_lows JSONB,
  bos_events JSONB,
  choch_events JSONB,
  no_trade_zones JSONB,
  volatility_state VARCHAR(32),
  raw_payload JSONB,
  strategy_config_version VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.3 candidate_plans

```sql
CREATE TABLE candidate_plans (
  id UUID PRIMARY KEY,
  structure_snapshot_id UUID REFERENCES market_structure_snapshots(id),
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  setup_type VARCHAR(64) NOT NULL,
  entry_zone JSONB,
  entry_price NUMERIC,
  stop_loss_price NUMERIC,
  take_profit_prices JSONB,
  risk_reward_ratio NUMERIC,
  opportunity_grade VARCHAR(16),
  status VARCHAR(32) NOT NULL,
  invalidation_reason TEXT,
  strategy_config_version VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.4 trade_plans

```sql
CREATE TABLE trade_plans (
  id UUID PRIMARY KEY,
  candidate_plan_id UUID REFERENCES candidate_plans(id),
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  setup_type VARCHAR(64),
  entry_price NUMERIC NOT NULL,
  stop_loss_price NUMERIC NOT NULL,
  take_profit_prices JSONB,
  leverage NUMERIC NOT NULL,
  margin_mode VARCHAR(32) DEFAULT 'isolated',
  risk_percent NUMERIC NOT NULL,
  opportunity_grade VARCHAR(16),
  status VARCHAR(32) NOT NULL,
  notes TEXT,
  risk_config_version VARCHAR(64),
  strategy_config_version VARCHAR(64),
  user_trading_config_version VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.5 position_sizing_results

```sql
CREATE TABLE position_sizing_results (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  equity NUMERIC NOT NULL,
  risk_percent NUMERIC NOT NULL,
  risk_amount NUMERIC NOT NULL,
  entry_price NUMERIC NOT NULL,
  stop_loss_price NUMERIC NOT NULL,
  stop_distance_percent NUMERIC NOT NULL,
  notional_value NUMERIC NOT NULL,
  raw_size NUMERIC,
  rounded_size NUMERIC,
  required_margin NUMERIC,
  leverage NUMERIC,
  estimated_fee NUMERIC,
  risk_reward_ratio NUMERIC,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.6 risk_checks

```sql
CREATE TABLE risk_checks (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  status VARCHAR(32) NOT NULL,
  max_allowed_risk_percent NUMERIC,
  block_reasons JSONB,
  warnings JSONB,
  payload JSONB,
  risk_config_version VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.7 ai_evaluations

```sql
CREATE TABLE ai_evaluations (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  candidate_plan_id UUID REFERENCES candidate_plans(id),
  model_name VARCHAR(128),
  input_payload JSONB,
  output_payload JSONB,
  recommended_action VARCHAR(32),
  warnings JSONB,
  ai_config_version VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.8 decision_gate_results

```sql
CREATE TABLE decision_gate_results (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  risk_check_id UUID REFERENCES risk_checks(id),
  ai_evaluation_id UUID REFERENCES ai_evaluations(id),
  result VARCHAR(32) NOT NULL,
  reasons JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.9 order_intents

```sql
CREATE TABLE order_intents (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  decision_gate_result_id UUID REFERENCES decision_gate_results(id),
  client_oid VARCHAR(128) UNIQUE NOT NULL,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  product_type VARCHAR(64),
  side VARCHAR(16),
  trade_side VARCHAR(16),
  order_type VARCHAR(32),
  price NUMERIC,
  size NUMERIC,
  margin_mode VARCHAR(32),
  leverage NUMERIC,
  stop_loss_price NUMERIC,
  take_profit_prices JSONB,
  status VARCHAR(32) NOT NULL,
  request_payload JSONB,
  request_hash VARCHAR(128),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.10 exchange_orders

```sql
CREATE TABLE exchange_orders (
  id UUID PRIMARY KEY,
  order_intent_id UUID REFERENCES order_intents(id),
  exchange_order_id VARCHAR(128),
  client_oid VARCHAR(128),
  exchange VARCHAR(32),
  symbol VARCHAR(32),
  status VARCHAR(32),
  filled_size NUMERIC,
  avg_fill_price NUMERIC,
  fee NUMERIC,
  raw_response JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.11 system_events

```sql
CREATE TABLE system_events (
  id UUID PRIMARY KEY,
  event_type VARCHAR(64) NOT NULL,
  severity VARCHAR(32) NOT NULL,
  entity_type VARCHAR(64),
  entity_id UUID,
  actor VARCHAR(32),
  message TEXT,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. 索引建议

```sql
CREATE INDEX idx_candles_symbol_tf_time ON candles(symbol, timeframe, open_time DESC);
CREATE INDEX idx_candidate_plans_status ON candidate_plans(status, created_at DESC);
CREATE INDEX idx_trade_plans_status ON trade_plans(status, created_at DESC);
CREATE INDEX idx_order_intents_status ON order_intents(status, created_at DESC);
CREATE INDEX idx_system_events_type_time ON system_events(event_type, created_at DESC);
```
