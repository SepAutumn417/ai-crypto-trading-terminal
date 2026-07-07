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

export interface CheckResult {
  plan: TradePlan;
  sizing: any;
  risk: any;
  decision: any;
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
};