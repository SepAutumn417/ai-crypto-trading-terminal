'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type CheckResult } from '@/lib/api';
import { SizingCard } from './SizingCard';
import { RiskCard } from './RiskCard';
import { DecisionCard } from './DecisionCard';
import { useState } from 'react';

export function PlanDetail({ planId }: { planId: string }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<CheckResult | null>(null);
  const { data: plan, isLoading } = useQuery({
    queryKey: ['plan', planId],
    queryFn: () => api.getPlan(planId),
  });
  const checkMut = useMutation({
    mutationFn: () => api.checkPlan(planId),
    onSuccess: (r) => { setResult(r); qc.invalidateQueries({ queryKey: ['plan', planId] }); qc.invalidateQueries({ queryKey: ['plans'] }); },
  });

  if (isLoading || !plan) return <p className="text-gray-500">加载中...</p>;

  return (
    <div className="space-y-4">
      <div className="p-4 border border-gray-800 rounded">
        <h3 className="text-lg font-bold mb-2">{plan.symbol} {plan.direction}</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>入场: {plan.entry_price}</div>
          <div>止损: {plan.stop_loss_price ?? '-'}</div>
          <div>杠杆: {plan.leverage}x</div>
          <div>风险: {plan.risk_percent}%</div>
          <div>等级: {plan.opportunity_grade}</div>
          <div>状态: <span className="font-bold">{plan.status}</span></div>
        </div>
        <button onClick={() => checkMut.mutate()} disabled={checkMut.isPending}
          className="mt-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 px-4 py-2 rounded">
          {checkMut.isPending ? '检查中...' : '运行检查'}
        </button>
      </div>
      {result && (
        <div className="space-y-3">
          <SizingCard sizing={result.sizing} />
          <RiskCard risk={result.risk} />
          <DecisionCard decision={result.decision} />
        </div>
      )}
    </div>
  );
}