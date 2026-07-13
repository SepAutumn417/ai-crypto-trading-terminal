'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, PlanCreate } from '@/lib/api';
import { PlanForm } from '@/components/plans/PlanForm';
import { PlanList } from '@/components/plans/PlanList';
import { PlanDetail } from '@/components/plans/PlanDetail';
import { useWebSocketInvalidation } from '@/lib/useWebSocket';

export default function PlansPage() {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const qc = useQueryClient();
  const { data: plans = [], isLoading, isError, error } = useQuery({ queryKey: ['plans'], queryFn: () => api.listPlans() });
  const createMut = useMutation({ mutationFn: (input: PlanCreate) => api.createPlan(input), onSuccess: () => qc.invalidateQueries({ queryKey: ['plans'] }) });
  useWebSocketInvalidation('plans', ['plans', 'plan']);
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">执行前检查</p><h1 className="page-title">交易计划</h1><p className="page-subtitle">把入场、止损、仓位与风险参数放在同一条可复核的决策链中。</p></div></header><div className="workflow-grid"><div className="surface workflow-panel space-y-5"><h2 className="surface-title">新建计划</h2><PlanForm onSubmit={(value) => createMut.mutate(value)} submitting={createMut.isPending} /><div className="pt-4 border-t border-slate-700"><h2 className="surface-title">计划列表</h2></div>{isError && <p className="text-red-300 text-sm">加载计划失败：{(error as Error).message}</p>}<PlanList plans={plans} loading={isLoading} onSelect={setSelectedPlanId} selectedId={selectedPlanId} /></div><div className="surface">{selectedPlanId ? <PlanDetail planId={selectedPlanId} /> : <div className="workflow-empty"><div><strong>从左侧选择一个计划</strong>查看完整决策、仓位规模与风险校验，或先创建新的交易计划。</div></div>}</div></div></div>;
}
