# 数据库设计初稿

## 1. 技术选择

推荐数据库：PostgreSQL。

推荐配套：

- Redis：缓存、任务队列、实时状态；
- JSONB：存储结构快照、AI输出、交易所响应。

---

## 2. 表总览

| 表 | 作用 | 首次引入版本 |
|---|---|---|
| `candles` | K线数据 | v0.2 |
| `market_structure_snapshots` | 市场结构快照 | v0.3 |
| `candidate_plans` | 自动候选交易计划 | v0.4 |
| `trade_plans` | 正式交易计划 | v0.1 |
| `position_sizing_results` | 仓位计算结果 | v0.1 |
| `risk_checks` | 风控检查结果 | v0.1 |
| `ai_evaluations` | AI评估结果 | v0.5 |
| `decision_gate_results` | 决策门结果 | v0.1 |
| `order_intents` | 内部订单意图 | v0.6 |
| `exchange_orders` | 交易所订单 | v0.6 |
| `order_state_events` | 订单状态事件 | v0.6 |
| `positions` | 持仓快照 | v0.7 |
| `trade_journal` | 交易日志 | v0.1（v0.1 plan 已建表） |
| `review_reports` | 复盘报告 | v1.0 |
| `config_versions` | 配置版本 | v0.1 |
| `system_events` | 系统事件 | v0.1 |
| `api_keys` | API Key元数据，不存明文 | v0.7 |
| `user_settings` | 用户设置 | v0.1 |
| `account_risk_state` | 账户风险状态（当日亏损/连亏/冷却期） | v0.1（v0.1 spec §4.2 新增） |

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

> 对齐 `CONFIG_VERSIONING.md §5`：每个订单意图必须记录 5 个配置版本，便于复盘时还原当时的风控/执行/AI/策略/用户配置。

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
  tp_sl_strategy VARCHAR(16),          -- preset（开仓时预设）/ post_fill（成交后设置），见 ADR-0006
  status VARCHAR(32) NOT NULL,
  request_payload JSONB,
  request_hash VARCHAR(128),
  -- 配置版本回溯（对齐 CONFIG_VERSIONING.md §5）
  risk_config_version VARCHAR(64),
  execution_config_version VARCHAR(64),
  user_trading_config_version VARCHAR(64),
  ai_config_version VARCHAR(64),
  strategy_config_version VARCHAR(64),
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

> 审计防篡改：`system_events` 增加 `prev_event_hash` 字段形成链式哈希，或使用 append-only 表 + 触发器禁止 UPDATE/DELETE。详见 `EVENT_LOG_DESIGN.md §5`。

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
  prev_event_hash VARCHAR(64),  -- 链式哈希，防篡改
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.12 order_state_events

> `ORDER_LIFECYCLE.md §5` 反复引用，记录订单状态机每次转换。

```sql
CREATE TABLE order_state_events (
  id UUID PRIMARY KEY,
  order_intent_id UUID NOT NULL REFERENCES order_intents(id),
  previous_status VARCHAR(32),
  next_status VARCHAR(32) NOT NULL,
  reason VARCHAR(128),
  actor VARCHAR(32) NOT NULL,  -- system / user / exchange
  raw_payload JSONB,
  raw_response JSONB,
  request_hash VARCHAR(128),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.13 positions

> v0.7 只读实盘同步引入，`API.md §10` Position APIs 依赖。

```sql
CREATE TABLE positions (
  id UUID PRIMARY KEY,
  exchange VARCHAR(32) NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  size NUMERIC NOT NULL,
  entry_price NUMERIC NOT NULL,
  mark_price NUMERIC,
  liquidation_price NUMERIC,
  leverage NUMERIC,
  margin_mode VARCHAR(32),
  margin NUMERIC,
  unrealized_pnl NUMERIC,
  realized_pnl NUMERIC,
  raw_payload JSONB,
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.14 trade_journal

> v0.1 plan 已建表，`FRONTEND_PAGES.md §9` Journal 页面依赖。

```sql
CREATE TABLE trade_journal (
  id UUID PRIMARY KEY,
  trade_plan_id UUID REFERENCES trade_plans(id),
  symbol VARCHAR(32) NOT NULL,
  direction VARCHAR(16) NOT NULL,
  entry_price NUMERIC,
  exit_price NUMERIC,
  size NUMERIC,
  pnl NUMERIC,
  actual_r NUMERIC,           -- 实际盈亏 R 倍数
  fee NUMERIC,
  status VARCHAR(32) NOT NULL DEFAULT 'OPEN',  -- OPEN / CLOSED / CANCELLED
  opened_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  notes TEXT,
  tags JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.15 review_reports

> v1.0 复盘统计依赖。

```sql
CREATE TABLE review_reports (
  id UUID PRIMARY KEY,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  total_trades INTEGER,
  winning_trades INTEGER,
  losing_trades INTEGER,
  breakeven_trades INTEGER,
  total_pnl NUMERIC,
  win_rate NUMERIC,
  avg_win NUMERIC,
  avg_loss NUMERIC,
  profit_factor NUMERIC,
  max_drawdown NUMERIC,
  summary TEXT,
  ai_summary TEXT,
  tags JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.16 config_versions

> v0.1 spec §4.2 已定义，此处补入 L4 文档包。部分唯一索引保证同一 `config_type` 仅一行 `is_active=true`。

```sql
CREATE TABLE config_versions (
  id UUID PRIMARY KEY,
  config_type VARCHAR(32) NOT NULL,      -- risk / execution / opportunity_grade / symbol_rules
  version_label VARCHAR(64) NOT NULL,    -- 例如 risk-v1
  payload JSONB NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  activated_at TIMESTAMPTZ,
  UNIQUE(config_type, version_label)
);
-- 部分唯一索引：同一 config_type 仅允许一行 is_active=true
CREATE UNIQUE INDEX idx_config_versions_active ON config_versions(config_type) WHERE is_active = true;
```

---

## 3.17 api_keys

> `SECURITY.md §2` 反复强调"加密保存"，此处补字段结构与加密说明。详见 `SECURITY.md §2.3 加密方案`。

```sql
CREATE TABLE api_keys (
  id UUID PRIMARY KEY,
  exchange VARCHAR(32) NOT NULL,         -- bitget / binance / okx
  key_id VARCHAR(128) NOT NULL,          -- 交易所返回的 apiKey（非敏感，用于查询）
  encrypted_secret BYTEA NOT NULL,       -- AES-256-GCM 加密后的 secret
  passphrase_encrypted BYTEA,            -- AES-256-GCM 加密后的 passphrase
  permissions JSONB NOT NULL,            -- ["read", "trade"]，不含 withdraw
  ip_whitelist JSONB,                    -- ["1.2.3.4"]
  key_version INTEGER NOT NULL DEFAULT 1,-- 主密钥版本，用于轮换
  status VARCHAR(32) NOT NULL DEFAULT 'active',  -- active / rotating / disabled
  rotating_since TIMESTAMPTZ,            -- 进入 rotating 态的时间，用于监控共存期（见 SECURITY.md §2.4.1）
  disabled_at TIMESTAMPTZ,               -- 进入 disabled 态的时间（轮换完成或主动禁用）
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 3.18 user_settings

> v0.1 spec §4.2 已定义，单行表。

```sql
CREATE TABLE user_settings (
  id UUID PRIMARY KEY,
  execution_enabled BOOLEAN NOT NULL DEFAULT false,
  kill_switch BOOLEAN NOT NULL DEFAULT true,   -- kill_switch=true 表示熔断态
  account_equity NUMERIC,                       -- v0.1 用户手动输入，v0.7 起交易所同步
  mode VARCHAR(32) DEFAULT 'training',          -- training / transition / standard / advanced
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  -- 单行表约束
  CHECK (id = '00000000-0000-0000-0000-000000000001')
);
```

---

## 3.19 account_risk_state

> v0.1 spec §4.2 新增，v0.1 plan 已建表。单行表，v0.1 为只读 seed，v0.8 接入真实成交后由 execution-engine 更新。

```sql
CREATE TABLE account_risk_state (
  id UUID PRIMARY KEY,
  daily_loss_r NUMERIC NOT NULL DEFAULT 0,
  consecutive_losses INTEGER NOT NULL DEFAULT 0,
  cooldown_until TIMESTAMPTZ,
  last_trade_date DATE,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  -- 单行表约束
  CHECK (id = '00000000-0000-0000-0000-000000000001')
);
```

---

## 4. 索引建议

> 索引需在 ORM 模型 `__table_args__` 与 Alembic 迁移中同步声明，避免测试环境（`Base.metadata.create_all()`）与生产行为不一致。

```sql
-- 行情
CREATE INDEX idx_candles_symbol_tf_time ON candles(exchange, symbol, timeframe, open_time DESC);

-- 候选计划
CREATE INDEX idx_candidate_plans_status ON candidate_plans(status, created_at DESC);

-- 交易计划
CREATE INDEX idx_trade_plans_status ON trade_plans(status, created_at DESC);

-- 仓位计算/风控/决策门结果（按 trade_plan_id 查最新一条）
CREATE INDEX idx_position_sizing_results_plan_id ON position_sizing_results(trade_plan_id);
CREATE INDEX idx_risk_checks_plan_id ON risk_checks(trade_plan_id);
CREATE INDEX idx_decision_gate_results_plan_id ON decision_gate_results(trade_plan_id);

-- 订单意图
CREATE INDEX idx_order_intents_status ON order_intents(status, created_at DESC);

-- 交易所订单
CREATE INDEX idx_exchange_orders_intent_id ON exchange_orders(order_intent_id);
CREATE INDEX idx_exchange_orders_exchange_oid ON exchange_orders(exchange, exchange_order_id);

-- 订单状态事件（按意图查事件流）
CREATE INDEX idx_order_state_events_intent_time ON order_state_events(order_intent_id, created_at);

-- 系统事件（按实体查事件 + 按类型查）
CREATE INDEX idx_system_events_type_time ON system_events(event_type, created_at DESC);
CREATE INDEX idx_system_events_entity ON system_events(entity_type, entity_id, created_at DESC);

-- 配置版本（部分唯一索引已在 §3.16 声明）
CREATE INDEX idx_config_versions_type_active ON config_versions(config_type, is_active);

-- 交易日志
CREATE INDEX idx_trade_journals_symbol ON trade_journal(symbol);
CREATE INDEX idx_trade_journals_status ON trade_journal(status);
CREATE INDEX idx_trade_journals_created_at ON trade_journal(created_at DESC);
```

---

## 5. NUMERIC 精度与约束

> 裸 `NUMERIC` 无精度上限会带来存储与计算开销。统一精度规范：

| 字段类型 | 精度规范 | 示例字段 |
|---|---|---|
| 价格 | `NUMERIC(28, 10)` | entry_price / stop_loss_price / price / mark_price |
| 数量 | `NUMERIC(28, 10)` | size / raw_size / rounded_size / filled_size |
| 金额 | `NUMERIC(20, 8)` | risk_amount / notional_value / required_margin / pnl / fee |
| 比例/倍数 | `NUMERIC(10, 6)` | risk_percent / stop_distance_percent / risk_reward_ratio / win_rate |
| R 值 | `NUMERIC(10, 4)` | daily_loss_r / actual_r |

约束建议：

- `trade_plans.status` 加 `CHECK (status IN ('DRAFT','CHECKED','READY_FOR_CONFIRMATION','SUBMITTING','SUBMITTED','PARTIALLY_FILLED','FILLED','TP_SL_PLACING','TP_SL_PLACED','POSITION_MONITORING','CLOSING','CLOSED','CANCELLED','REJECTED','FAILED','EXPIRED'))`；
- `trade_plans.leverage > 0`；
- `trade_plans.risk_percent > 0`；
- `order_intents.leverage > 0`；
- 单行表（`user_settings` / `account_risk_state`）用 `CHECK (id = '00000000-0000-0000-0000-000000000001')` 强制；
- 外键级联策略：默认 `ON DELETE RESTRICT`，仅日志/事件类表可 `ON DELETE SET NULL`。

---

## 6. 迁移与 Schema 演进

- 使用 Alembic 管理 schema 演进，迁移文件存放于 `apps/api/migrations/versions/`；
- `alembic.ini` 中 `sqlalchemy.url` 留空，全部从 `env.py` 的 `settings.database_url` 注入；
- ORM 模型与迁移必须保持一致：新增索引需同时写在 ORM `__table_args__` 与迁移中，避免 `alembic autogenerate` 重复生成；
- 向后兼容策略：新增列必须 `NULLABLE` 或有 `DEFAULT`；删除列需先标记 deprecated 一个版本，下个版本再删；
- 详见 `MIGRATION_POLICY.md`（待新增）。
