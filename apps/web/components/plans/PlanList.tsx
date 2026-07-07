'use client';
import type { TradePlan } from '@/lib/api';
import { cn } from '@/lib/utils';

const statusStyles: Record<string, string> = {
  DRAFT: 'bg-gray-700 text-gray-300',
  CHECKED: 'bg-blue-900 text-blue-300',
  APPROVED: 'bg-green-900 text-green-300',
  REJECTED: 'bg-red-900 text-red-300',
  SUBMITTED: 'bg-yellow-900 text-yellow-300',
  FILLED: 'bg-emerald-900 text-emerald-300',
  CLOSED: 'bg-gray-800 text-gray-400',
  CANCELLED: 'bg-gray-800 text-gray-500',
};

const gradeStyles: Record<string, string> = {
  A: 'text-green-400',
  B: 'text-yellow-400',
  C: 'text-orange-400',
  BLOCKED: 'text-red-400',
};

function formatDate(iso: string) {
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${m}-${day} ${h}:${min}`;
}

export function PlanList({ plans, loading, onSelect, selectedId }: {
  plans: TradePlan[]; loading: boolean;
  onSelect: (id: string) => void; selectedId: string | null;
}) {
  if (loading) return <p className="text-gray-500">加载中...</p>;
  if (plans.length === 0) return <p className="text-gray-500">暂无计划</p>;

  return (
    <div className="space-y-2 max-h-[600px] overflow-y-auto">
      {plans.map((p) => (
        <button key={p.id} onClick={() => onSelect(p.id)}
          className={cn(
            'w-full text-left p-3 border rounded transition-colors',
            selectedId === p.id ? 'border-blue-500 bg-blue-950' : 'border-gray-800 hover:bg-gray-900'
          )}>
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded font-mono',
                p.direction === 'LONG' ? 'bg-green-900/60 text-green-400' : 'bg-red-900/60 text-red-400'
              )}>
                {p.direction}
              </span>
              <span className="font-bold">{p.symbol}</span>
              <span className={cn('text-sm font-semibold', gradeStyles[p.opportunity_grade] || 'text-gray-400')}>
                {p.opportunity_grade}
              </span>
            </div>
            <span className={cn(
              'text-xs px-2 py-0.5 rounded-full',
              statusStyles[p.status] || 'bg-gray-700 text-gray-300'
            )}>
              {p.status}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
            <div>入场: <span className="text-gray-300">{p.entry_price}</span></div>
            <div>止损: <span className="text-gray-300">{p.stop_loss_price ?? '-'}</span></div>
            <div>杠杆: <span className="text-gray-300">{p.leverage}x</span></div>
            <div>风险: <span className="text-gray-300">{p.risk_percent}%</span></div>
            <div>TP数: <span className="text-gray-300">{p.take_profit_prices.length}</span></div>
            <div className="text-right text-gray-600">{formatDate(p.created_at)}</div>
          </div>
        </button>
      ))}
    </div>
  );
}