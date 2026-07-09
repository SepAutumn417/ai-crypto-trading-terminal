'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type CandidatePlan, type KlineInterval } from '@/lib/api';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const INTERVALS: { label: string; value: KlineInterval }[] = [
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '4h', value: '4h' },
  { label: '1d', value: '1d' },
];

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-600 text-white',
  B: 'bg-blue-600 text-white',
  C: 'bg-yellow-600 text-white',
  BLOCKED: 'bg-red-600 text-white',
};

const STATUS_COLORS: Record<string, string> = {
  DISCOVERED: 'bg-gray-700 text-gray-300',
  WATCHING: 'bg-blue-900 text-blue-300',
  READY: 'bg-green-900 text-green-300',
  RISK_CHECKED: 'bg-cyan-900 text-cyan-300',
  AI_EVALUATED: 'bg-purple-900 text-purple-300',
  ALLOW_CONFIRM: 'bg-green-600 text-white',
  WAIT: 'bg-yellow-900 text-yellow-300',
  BLOCK: 'bg-red-900 text-red-300',
  EXPIRED: 'bg-gray-800 text-gray-500',
};

const SETUP_LABELS: Record<string, string> = {
  TREND_PULLBACK_LONG: '趋势回踩做多',
  TREND_PULLBACK_SHORT: '趋势反抽做空',
  RANGE_SUPPORT_BOUNCE: '震荡支撑反弹',
  RANGE_RESISTANCE_REJECT: '震荡阻力回落',
  BREAKOUT_RETEST_LONG: '突破回踩做多',
  BREAKDOWN_RETEST_SHORT: '跌破反抽做空',
  FALSE_BREAK_REVERSAL: '假突破反转',
};

export function OpportunityRadar() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState<KlineInterval>('1h');
  const [gradeFilter, setGradeFilter] = useState<string>('');
  const [promoteTarget, setPromoteTarget] = useState<CandidatePlan | null>(null);
  const qc = useQueryClient();

  const { data: scanResult, isLoading: scanning, error: scanError, mutate: scan } = useMutation({
    mutationFn: () => api.scanCandidates(symbol, interval, 200),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['candidates'] });
    },
  });

  const { data: candidateList, isLoading: listLoading } = useQuery({
    queryKey: ['candidates', gradeFilter],
    queryFn: () => api.listCandidates(gradeFilter ? { grade: gradeFilter, limit: 100 } : { limit: 100 }),
    refetchInterval: 30000,
  });

  const { mutate: promote, isPending: promoting } = useMutation({
    mutationFn: ({ id, input }: { id: string; input: { leverage: string; risk_percent: string; equity: string; margin_mode: string } }) =>
      api.promoteCandidate(id, input),
    onSuccess: () => {
      setPromoteTarget(null);
      qc.invalidateQueries({ queryKey: ['candidates'] });
      qc.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const candidates = scanResult?.candidates ?? candidateList?.items ?? [];

  return (
    <div className="space-y-6">
      {/* 扫描控制 */}
      <div className="bg-gray-900 rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-3">Opportunity Radar</h2>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex gap-2">
            {SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  symbol === s ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {INTERVALS.map((i) => (
              <button
                key={i.value}
                onClick={() => setInterval(i.value)}
                className={`px-3 py-1.5 rounded text-sm transition-colors ${
                  interval === i.value ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {i.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => scan()}
            disabled={scanning}
            className="px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scanning ? '扫描中...' : '扫描机会'}
          </button>
        </div>

        {scanResult && (
          <div className="mt-3 flex gap-4 text-sm text-gray-400">
            <span>市场状态：<span className="text-white">{scanResult.market_state}</span></span>
            <span>趋势方向：<span className="text-white">{scanResult.trend_direction}</span></span>
            <span>发现候选：<span className="text-white">{scanResult.total}</span></span>
          </div>
        )}
        {scanError && (
          <p className="mt-2 text-red-400 text-sm">扫描失败：{(scanError as Error).message}</p>
        )}
      </div>

      {/* 过滤器 */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-400">评级过滤：</span>
        {['', 'A', 'B', 'C'].map((g) => (
          <button
            key={g || 'all'}
            onClick={() => setGradeFilter(g)}
            className={`px-2 py-1 rounded text-xs transition-colors ${
              gradeFilter === g ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {g || '全部'}
          </button>
        ))}
      </div>

      {/* 候选计划列表 */}
      <div className="space-y-3">
        {listLoading && candidates.length === 0 && (
          <p className="text-gray-400 text-sm">加载中...</p>
        )}
        {candidates.length === 0 && !listLoading && (
          <div className="bg-gray-900 rounded-lg p-8 text-center text-gray-500">
            暂无候选计划，点击「扫描机会」生成
          </div>
        )}
        {candidates.map((c) => (
          <CandidateCard
            key={c.id}
            candidate={c}
            onPromote={() => setPromoteTarget(c)}
          />
        ))}
      </div>

      {/* Promote 弹窗 */}
      {promoteTarget && (
        <PromoteModal
          candidate={promoteTarget}
          pending={promoting}
          onClose={() => setPromoteTarget(null)}
          onConfirm={(input) => promote({ id: promoteTarget.id, input })}
        />
      )}
    </div>
  );
}

function CandidateCard({ candidate: c, onPromote }: { candidate: CandidatePlan; onPromote: () => void }) {
  const promotable = ['READY', 'RISK_CHECKED', 'AI_EVALUATED', 'ALLOW_CONFIRM'].includes(c.status);

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${GRADE_COLORS[c.opportunity_grade] || 'bg-gray-700'}`}>
            {c.opportunity_grade}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[c.status] || 'bg-gray-700'}`}>
            {c.status}
          </span>
          <span className="text-white font-medium">{c.symbol}</span>
          <span className={`text-sm ${c.direction === 'long' ? 'text-green-400' : 'text-red-400'}`}>
            {c.direction === 'long' ? '做多' : '做空'}
          </span>
        </div>
        <span className="text-xs text-gray-500">{SETUP_LABELS[c.setup_type] || c.setup_type}</span>
      </div>

      <p className="text-sm text-gray-400 mb-3">{c.rationale}</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <span className="text-gray-500">入场区</span>
          <p className="text-white">{c.entry_zone.lower} - {c.entry_zone.upper}</p>
        </div>
        <div>
          <span className="text-gray-500">止损</span>
          <p className="text-red-400">{c.stop_loss_price}</p>
        </div>
        <div>
          <span className="text-gray-500">止盈</span>
          <p className="text-green-400">{c.take_profit_prices.join(', ') || '-'}</p>
        </div>
        <div>
          <span className="text-gray-500">盈亏比</span>
          <p className="text-white">{c.risk_reward_ratio || '-'}</p>
        </div>
      </div>

      {c.invalidation_reason && (
        <p className="mt-2 text-xs text-red-400">失效原因：{c.invalidation_reason}</p>
      )}

      {promotable && (
        <div className="mt-3 flex justify-end">
          <button
            onClick={onPromote}
            className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-500"
          >
            提升为交易计划
          </button>
        </div>
      )}
    </div>
  );
}

function PromoteModal({
  candidate,
  pending,
  onClose,
  onConfirm,
}: {
  candidate: CandidatePlan;
  pending: boolean;
  onClose: () => void;
  onConfirm: (input: { leverage: string; risk_percent: string; equity: string; margin_mode: string }) => void;
}) {
  const [leverage, setLeverage] = useState('5');
  const [riskPercent, setRiskPercent] = useState('1.0');
  const [equity, setEquity] = useState('10000');
  const [marginMode, setMarginMode] = useState('isolated');

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-gray-900 rounded-lg p-6 max-w-md w-full mx-4 border border-gray-700"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold mb-1">提升候选计划</h3>
        <p className="text-sm text-gray-400 mb-4">
          {candidate.symbol} {candidate.direction === 'long' ? '做多' : '做空'} · {SETUP_LABELS[candidate.setup_type] || candidate.setup_type}
        </p>

        <div className="space-y-3">
          <div>
            <label className="block text-sm text-gray-400 mb-1">杠杆倍数</label>
            <input
              type="number"
              value={leverage}
              onChange={(e) => setLeverage(e.target.value)}
              className="w-full bg-gray-800 rounded px-3 py-2 text-white text-sm border border-gray-700"
              min="1"
              max="125"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">风险百分比 (%)</label>
            <input
              type="number"
              value={riskPercent}
              onChange={(e) => setRiskPercent(e.target.value)}
              className="w-full bg-gray-800 rounded px-3 py-2 text-white text-sm border border-gray-700"
              min="0.1"
              max="10"
              step="0.1"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">账户权益 (USDT)</label>
            <input
              type="number"
              value={equity}
              onChange={(e) => setEquity(e.target.value)}
              className="w-full bg-gray-800 rounded px-3 py-2 text-white text-sm border border-gray-700"
              min="1"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">保证金模式</label>
            <select
              value={marginMode}
              onChange={(e) => setMarginMode(e.target.value)}
              className="w-full bg-gray-800 rounded px-3 py-2 text-white text-sm border border-gray-700"
            >
              <option value="isolated">逐仓</option>
              <option value="crossed">全仓</option>
            </select>
          </div>
        </div>

        <div className="mt-4 bg-gray-800 rounded p-3 text-sm">
          <div className="flex justify-between text-gray-400">
            <span>入场价</span>
            <span className="text-white">{candidate.entry_price || '-'}</span>
          </div>
          <div className="flex justify-between text-gray-400 mt-1">
            <span>止损价</span>
            <span className="text-red-400">{candidate.stop_loss_price}</span>
          </div>
          <div className="flex justify-between text-gray-400 mt-1">
            <span>止盈价</span>
            <span className="text-green-400">{candidate.take_profit_prices.join(', ')}</span>
          </div>
        </div>

        <div className="mt-4 flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded text-sm hover:bg-gray-600"
          >
            取消
          </button>
          <button
            onClick={() => onConfirm({ leverage, risk_percent: riskPercent, equity, margin_mode: marginMode })}
            disabled={pending}
            className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-500 disabled:opacity-50"
          >
            {pending ? '提交中...' : '确认提升'}
          </button>
        </div>
      </div>
    </div>
  );
}
