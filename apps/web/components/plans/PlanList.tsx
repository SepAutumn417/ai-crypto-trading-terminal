'use client';
import type { TradePlan } from '@/lib/api';
import { cn } from '@/lib/utils';

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
            'w-full text-left p-3 border rounded',
            selectedId === p.id ? 'border-blue-500 bg-blue-950' : 'border-gray-800 hover:bg-gray-900'
          )}>
          <div className="flex justify-between">
            <span className="font-bold">{p.symbol} {p.direction}</span>
            <span className="text-xs text-gray-400">{p.status}</span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {p.opportunity_grade} | {p.entry_price} | SL {p.stop_loss_price ?? '-'}
          </div>
        </button>
      ))}
    </div>
  );
}