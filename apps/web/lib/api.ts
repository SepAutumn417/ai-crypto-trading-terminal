const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string; details?: any } | null;
  request_id: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new Error(body.error?.message || 'API error');
  }
  return body.data as T;
}

export interface SystemStatus {
  execution_enabled: boolean;
  kill_switch: boolean;
  db_healthy: boolean;
  latest_event_type?: string | null;
  latest_event_at?: string | null;
}

export interface UserSettings {
  execution_enabled: boolean;
  kill_switch: boolean;
  account_equity: string | null;
  mode: string;
}

export interface ConfigVersion {
  id: string;
  config_type: string;
  version_label: string;
  payload: Record<string, any>;
  is_active: boolean;
  created_at: string;
  activated_at: string | null;
}

export interface ActiveConfigs {
  risk?: ConfigVersion | null;
  execution?: ConfigVersion | null;
  opportunity_grade?: ConfigVersion | null;
  symbol_rules?: ConfigVersion | null;
}

export interface TradePlan {
  id: string;
  exchange: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: string;
  stop_loss_price: string | null;
  take_profit_prices: string[];
  leverage: string;
  margin_mode: string;
  risk_percent: string;
  opportunity_grade: 'A' | 'B' | 'C' | 'BLOCKED';
  equity: string;
  setup_type: string | null;
  notes: string | null;
  status: string;
  risk_config_version: string | null;
  strategy_config_version: string | null;
  user_trading_config_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlanCreate {
  exchange?: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: string;
  stop_loss_price?: string | null;
  take_profit_prices: string[];
  leverage: string;
  risk_percent: string;
  opportunity_grade: 'A' | 'B' | 'C' | 'BLOCKED';
  equity: string;
  setup_type?: string | null;
  margin_mode?: string;
  notes?: string | null;
}

export interface PositionSizingResult {
  id: string | null;
  trade_plan_id: string | null;
  equity: string;
  risk_percent: string;
  risk_amount: string;
  entry_price: string;
  stop_loss_price: string | null;
  stop_distance_percent: string;
  notional_value: string;
  raw_size: string;
  rounded_size: string | null;
  required_margin: string;
  leverage: string;
  estimated_fee: string;
  risk_reward_ratio: string;
  estimated_loss_at_stop: string;
  sizing_warnings: string[];
}

export interface RiskCheckResult {
  id: string | null;
  trade_plan_id: string | null;
  status: string;
  risk_amount: string;
  notional_value: string;
  required_margin: string;
  risk_reward_ratio: string;
  max_allowed_risk_percent: string;
  warnings: string[];
  block_reasons: string[];
  risk_config_version: string | null;
}

export interface DecisionGateResult {
  id: string | null;
  trade_plan_id: string | null;
  risk_check_id: string | null;
  result: string;
  reasons: string[];
}

export interface CheckResult {
  plan: TradePlan;
  sizing: PositionSizingResult;
  risk: RiskCheckResult;
  decision: DecisionGateResult;
}

export interface Ticker {
  symbol: string;
  last_price: string;
  mark_price: string | null;
  index_price: string | null;
  high_24h: string | null;
  low_24h: string | null;
  volume_24h: string | null;
  change_percent_24h: string | null;
  timestamp: string | null;
}

export interface Kline {
  timestamp: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  quote_volume: string | null;
}

export interface OrderbookLevel {
  price: string;
  quantity: string;
}

export interface Orderbook {
  symbol: string;
  bids: OrderbookLevel[];
  asks: OrderbookLevel[];
  timestamp: string | null;
}

export type KlineInterval = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '6h' | '12h' | '1d' | '1w';

export interface TradeJournal {
  id: string;
  trade_plan_id: string | null;
  exchange: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: string;
  exit_price: string | null;
  quantity: string;
  leverage: string;
  pnl: string | null;
  pnl_percent: string | null;
  setup_type: string | null;
  entry_reason: string | null;
  exit_reason: string | null;
  lessons_learned: string | null;
  emotions: string | null;
  status: 'OPEN' | 'CLOSED';
  entry_at: string | null;
  exit_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TradeJournalCreate {
  trade_plan_id?: string | null;
  exchange?: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  entry_price: string;
  exit_price?: string | null;
  quantity: string;
  leverage?: string;
  pnl?: string | null;
  pnl_percent?: string | null;
  setup_type?: string | null;
  entry_reason?: string | null;
  exit_reason?: string | null;
  lessons_learned?: string | null;
  emotions?: string | null;
  status?: 'OPEN' | 'CLOSED';
  entry_at?: string | null;
  exit_at?: string | null;
}

export interface TradeJournalSummary {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: string | null;
  total_pnl: string;
  avg_pnl: string | null;
  best_trade: string | null;
  worst_trade: string | null;
}

export interface AIIndicatorSignal {
  name: string;
  value: string | null;
  signal: 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'strong_sell';
  weight: string;
  score: string;
  explanation: string;
}

export interface AIEvaluationResult {
  symbol: string;
  direction: string;
  overall_score: string;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  recommendation: string;
  signals: AIIndicatorSignal[];
  summary: string;
  risk_level: string;
  conviction: string;
}

export const api = {
  getSystemStatus: () => request<SystemStatus>('/api/system/status'),
  toggleKillSwitch: (enabled: boolean) =>
    request<UserSettings>('/api/system/kill-switch', { method: 'POST', body: JSON.stringify({ enabled }) }),
  toggleExecutionMode: (enabled: boolean) =>
    request<UserSettings>('/api/system/execution-mode', { method: 'POST', body: JSON.stringify({ enabled }) }),
  getUserSettings: async (): Promise<UserSettings> => {
    const s = await request<SystemStatus>('/api/system/status');
    return {
      execution_enabled: s.execution_enabled,
      kill_switch: s.kill_switch,
      account_equity: null,
      mode: 'training',
    };
  },
  getActiveConfigs: () => request<ActiveConfigs>('/api/configs/active'),
  listConfigs: (type: string) => request<ConfigVersion[]>(`/api/configs?type=${type}`),
  createConfig: (input: { config_type: string; version_label: string; payload: any }) =>
    request<ConfigVersion>('/api/configs', { method: 'POST', body: JSON.stringify(input) }),
  activateConfig: (id: string) =>
    request<ConfigVersion>(`/api/configs/${id}/activate`, { method: 'POST' }),
  createPlan: (input: PlanCreate) =>
    request<TradePlan>('/api/trade-plans', { method: 'POST', body: JSON.stringify(input) }),
  checkPlan: (id: string) =>
    request<CheckResult>(`/api/trade-plans/${id}/check`, { method: 'POST' }),
  listPlans: (status?: string) =>
    request<TradePlan[]>(status ? `/api/trade-plans?status=${status}` : '/api/trade-plans'),
  getPlan: (id: string) => request<TradePlan>(`/api/trade-plans/${id}`),
  calculatePosition: (input: any) =>
    request<any>('/api/risk/calculate-position', { method: 'POST', body: JSON.stringify(input) }),
  getTicker: (symbol: string) =>
    request<Ticker>(`/api/market/ticker?symbol=${encodeURIComponent(symbol)}`),
  getKlines: (symbol: string, interval: KlineInterval = '1h', limit: number = 100) =>
    request<Kline[]>(`/api/market/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`),
  getOrderbook: (symbol: string, limit: number = 20) =>
    request<Orderbook>(`/api/market/orderbook?symbol=${encodeURIComponent(symbol)}&limit=${limit}`),
  getJournals: (params?: { page?: number; page_size?: number; symbol?: string; status?: string }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set('page', String(params.page));
    if (params?.page_size) qs.set('page_size', String(params.page_size));
    if (params?.symbol) qs.set('symbol', params.symbol);
    if (params?.status) qs.set('status', params.status);
    return request<{ items: TradeJournal[]; total: number; page: number; page_size: number }>(
      `/api/journals?${qs.toString()}`
    );
  },
  getJournal: (id: string) => request<TradeJournal>(`/api/journals/${id}`),
  createJournal: (data: TradeJournalCreate) =>
    request<TradeJournal>('/api/journals', { method: 'POST', body: JSON.stringify(data) }),
  updateJournal: (id: string, data: Partial<TradeJournalCreate>) =>
    request<TradeJournal>(`/api/journals/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteJournal: (id: string) => request<{ deleted: boolean }>(`/api/journals/${id}`, { method: 'DELETE' }),
  getJournalSummary: (symbol?: string) =>
    request<TradeJournalSummary>(`/api/journals/summary${symbol ? `?symbol=${symbol}` : ''}`),
  evaluateOpportunity: (params: {
    symbol: string;
    direction: 'LONG' | 'SHORT';
    entry_price: string;
    interval?: KlineInterval;
    limit?: number;
  }) => {
    const qs = new URLSearchParams();
    qs.set('symbol', params.symbol);
    qs.set('direction', params.direction);
    qs.set('entry_price', params.entry_price);
    if (params.interval) qs.set('interval', params.interval);
    if (params.limit) qs.set('limit', String(params.limit));
    return request<AIEvaluationResult>(`/api/ai/evaluate?${qs.toString()}`);
  },
};