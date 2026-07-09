// 自动生成的类型（由 openapi-typescript 从 FastAPI OpenAPI schema 生成）
// 运行 `pnpm --filter web generate-types` 重新生成（需先 `python scripts/export_openapi.py`）
import type { components } from './api-types';

type Schema = components['schemas'];

// 枚举类型直接使用生成类型（单一数据源）
export type Direction = Schema['Direction'];
export type EvaluationGrade = Schema['EvaluationGrade'];
export type SignalType = Schema['SignalType'];
export type KlineInterval = Schema['KlineInterval'];
export type OpportunityGrade = Schema['OpportunityGrade'];

// AI 评估相关类型已与生成类型完全匹配，直接复用
export type AIIndicatorSignal = Schema['IndicatorResult'];
export type AIEvaluationResult = Schema['AIEvaluationResult'];

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';
const DEFAULT_TIMEOUT_MS = 15_000;

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string; details?: any } | null;
  request_id: string;
}

export class ApiError extends Error {
  code: string;
  requestId: string;
  statusCode: number;
  constructor(message: string, code: string, requestId: string, statusCode: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.requestId = requestId;
    this.statusCode = statusCode;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('请求超时', 'TIMEOUT', '', 408);
    }
    throw new ApiError(`网络错误: ${(e as Error).message}`, 'NETWORK_ERROR', '', 0);
  }
  clearTimeout(timeoutId);

  // 非 JSON 响应（如 5xx HTML）兜底
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new ApiError(`服务器错误 (HTTP ${res.status})`, 'HTTP_ERROR', '', res.status);
  }

  const body: ApiResponse<T> = await res.json();
  if (!body.success) {
    throw new ApiError(
      body.error?.message || 'API error',
      body.error?.code || 'UNKNOWN',
      body.request_id || '',
      res.status,
    );
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

export interface CreateConfigInput {
  config_type: 'risk' | 'execution' | 'opportunity_grade' | 'symbol_rules';
  version_label: string;
  payload: Record<string, unknown>;
}

export interface CalculatePositionInput {
  equity: string;
  risk_percent: string;
  entry_price: string;
  stop_loss_price?: string | null;
  take_profit_prices?: string[];
  leverage: string;
  fee_rate: string;
  direction: Direction;
  symbol: string;
}

export interface CalculatePositionResult {
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

export interface TradePlan {
  id: string;
  exchange: string;
  symbol: string;
  direction: Direction;
  entry_price: string;
  stop_loss_price: string | null;
  take_profit_prices: string[];
  leverage: string;
  margin_mode: string;
  risk_percent: string;
  opportunity_grade: OpportunityGrade;
  equity: string;
  setup_type: string | null;
  notes: string | null;
  status: string;
  candidate_plan_id: string | null;
  risk_config_version: string | null;
  strategy_config_version: string | null;
  user_trading_config_version: string | null;
  exchange_order_id: string | null;
  client_order_id: string | null;
  filled_quantity: string | null;
  average_fill_price: string | null;
  execution_error: string | null;
  execution_attempts: number;
  execution_error_code: string | null;
  execution_retryable: boolean | null;
  execution_retry_after_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface PlanCreate {
  exchange?: string;
  symbol: string;
  direction: Direction;
  entry_price: string;
  stop_loss_price?: string | null;
  take_profit_prices: string[];
  leverage: string;
  risk_percent: string;
  opportunity_grade: OpportunityGrade;
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

// v0.3: 市场结构识别类型
export interface SwingPoint {
  id: string;
  type: 'high' | 'low';
  index: number;
  price: string;
  timestamp: string;
  confirmed: boolean;
  structure_label: string | null;
}

export interface BosEvent {
  id: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  broken_swing_id: string;
  broken_price: string;
  break_index: number;
  break_timestamp: string;
  close_price: string;
}

export interface ChochEvent {
  id: string;
  direction: 'bullish' | 'bearish' | 'neutral';
  broken_swing_id: string;
  broken_price: string;
  break_index: number;
  break_timestamp: string;
  close_price: string;
}

export interface PriceZone {
  id: string;
  zone_type: 'support' | 'resistance' | 'no_trade';
  upper: string;
  lower: string;
  midpoint: string;
  strength: number;
  swing_ids: string[];
  formed_at: string | null;
  last_tested_at: string | null;
}

export interface MarketStructureSnapshot {
  id: string;
  symbol: string;
  timeframe: string;
  captured_at: string;
  kline_count: number;
  kline_start: string | null;
  kline_end: string | null;
  market_state: 'trend' | 'range' | 'transition';
  trend_direction: 'bullish' | 'bearish' | 'neutral';
  swing_highs: SwingPoint[];
  swing_lows: SwingPoint[];
  bos_events: BosEvent[];
  choch_events: ChochEvent[];
  support_zones: PriceZone[];
  resistance_zones: PriceZone[];
  no_trade_zones: PriceZone[];
  volatility_state: 'low' | 'normal' | 'high';
  last_price: string | null;
  config: Record<string, unknown>;
}

// v0.4: 候选计划类型
export interface CandidatePlan {
  id: string;
  structure_snapshot_id: string | null;
  exchange: string;
  symbol: string;
  timeframe: string;
  direction: 'long' | 'short';
  setup_type: string;
  entry_zone: { upper: string; lower: string };
  entry_price: string | null;
  stop_loss_price: string;
  take_profit_prices: string[];
  risk_reward_ratio: string | null;
  opportunity_grade: string;
  status: string;
  invalidation_reason: string | null;
  rationale: string;
  structure_signals: Record<string, unknown>;
  strategy_config_version: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanResult {
  symbol: string;
  timeframe: string;
  market_state: string;
  trend_direction: string;
  candidates: CandidatePlan[];
  total: number;
  skipped_duplicates?: number;
}

export interface CandidateListResponse {
  items: CandidatePlan[];
  total: number;
  page: number;
  page_size: number;
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

export interface TradeJournal {
  id: string;
  trade_plan_id: string | null;
  exchange: string;
  symbol: string;
  direction: Direction;
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
  direction: Direction;
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

export const api = {
  getSystemStatus: () => request<SystemStatus>('/api/system/status'),
  toggleKillSwitch: (enabled: boolean) =>
    request<UserSettings>('/api/system/kill-switch', { method: 'POST', body: JSON.stringify({ enabled }) }),
  toggleExecutionMode: (enabled: boolean) =>
    request<UserSettings>('/api/system/execution-mode', { method: 'POST', body: JSON.stringify({ enabled }) }),
  getUserSettings: () => request<UserSettings>('/api/system/user-settings'),
  updateUserSettings: (input: { account_equity?: string | null; mode?: string | null }) =>
    request<UserSettings>('/api/system/user-settings', { method: 'PUT', body: JSON.stringify(input) }),
  getActiveConfigs: () => request<ActiveConfigs>('/api/configs/active'),
  listConfigs: (type: string) => request<ConfigVersion[]>(`/api/configs?type=${type}`),
  createConfig: (input: CreateConfigInput) =>
    request<ConfigVersion>('/api/configs', { method: 'POST', body: JSON.stringify(input) }),
  activateConfig: (id: string) =>
    request<ConfigVersion>(`/api/configs/${id}/activate`, { method: 'POST' }),
  createPlan: (input: PlanCreate) =>
    request<TradePlan>('/api/trade-plans', { method: 'POST', body: JSON.stringify(input) }),
  checkPlan: (id: string) =>
    request<CheckResult>(`/api/trade-plans/${id}/check`, { method: 'POST' }),
  executePlan: (id: string) =>
    request<TradePlan>(`/api/trade-plans/${id}/execute`, { method: 'POST' }),
  syncOrderStatus: (id: string) =>
    request<TradePlan>(`/api/trade-plans/${id}/sync`, { method: 'POST' }),
  cancelPlanOrder: (id: string) =>
    request<TradePlan>(`/api/trade-plans/${id}/cancel`, { method: 'POST' }),
  listPlans: (status?: string) =>
    request<TradePlan[]>(status ? `/api/trade-plans?status=${status}` : '/api/trade-plans'),
  getPlan: (id: string) => request<TradePlan>(`/api/trade-plans/${id}`),
  calculatePosition: (input: CalculatePositionInput) =>
    request<CalculatePositionResult>('/api/risk/calculate-position', { method: 'POST', body: JSON.stringify(input) }),
  getTicker: (symbol: string) =>
    request<Ticker>(`/api/market/ticker?symbol=${encodeURIComponent(symbol)}`),
  getKlines: (symbol: string, interval: KlineInterval = '1h', limit: number = 100) =>
    request<Kline[]>(`/api/market/klines?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`),
  getOrderbook: (symbol: string, limit: number = 20) =>
    request<Orderbook>(`/api/market/orderbook?symbol=${encodeURIComponent(symbol)}&limit=${limit}`),
  getMarketStructure: (symbol: string, interval: KlineInterval = '1h', limit: number = 200) =>
    request<MarketStructureSnapshot>(`/api/market/structure?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`),
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
    direction: Direction;
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
  scanCandidates: (symbol: string, interval: KlineInterval = '1h', limit: number = 200) => {
    const qs = new URLSearchParams();
    qs.set('symbol', symbol);
    qs.set('interval', interval);
    qs.set('limit', String(limit));
    return request<ScanResult>(`/api/auto-plans/scan?${qs.toString()}`, { method: 'POST' });
  },
  listCandidates: (params?: { status?: string; symbol?: string; grade?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status', params.status);
    if (params?.symbol) qs.set('symbol', params.symbol);
    if (params?.grade) qs.set('grade', params.grade);
    if (params?.limit) qs.set('limit', String(params.limit));
    return request<CandidateListResponse>(`/api/auto-plans?${qs.toString()}`);
  },
  getCandidate: (id: string) => request<CandidatePlan>(`/api/auto-plans/${id}`),
  promoteCandidate: (id: string, input: {
    leverage: string;
    risk_percent: string;
    equity: string;
    margin_mode?: string;
    notes?: string;
  }) => request<{ candidate_id: string; trade_plan_id: string; status: string; message: string }>(
    `/api/auto-plans/${id}/promote`,
    { method: 'POST', body: JSON.stringify(input) },
  ),
};