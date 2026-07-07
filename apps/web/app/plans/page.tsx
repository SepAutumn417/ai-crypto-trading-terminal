'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, PlanCreate } from '@/lib/api';
import { PlanForm } from '@/components/plans/PlanForm';
import { PlanList } from '@/components/plans/PlanList';
import { PlanDetail } from '@/components/plans/PlanDetail';

export default function PlansPage() {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const qc = useQueryClient();
  const { data: plans = [], isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => api.listPlans(),
  });
  const createMut = useMutation({
    mutationFn: (input: PlanCreate) => api.createPlan(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plans'] }),
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1 space-y-4">
        <h2 className="text-xl font-bold">新建计划</h2>
        <PlanForm onSubmit={(v) => createMut.mutate(v)} submitting={createMut.isPending} />
        <h2 className="text-xl font-bold mt-6">计划列表</h2>
        <PlanList plans={plans} loading={isLoading} onSelect={setSelectedPlanId} selectedId={selectedPlanId} />
      </div>
      <div className="lg:col-span-2">
        {selectedPlanId ? <PlanDetail planId={selectedPlanId} /> : (
          <p className="text-gray-500">从左侧选择计划以查看详情，或新建一个。</p>
        )}
      </div>
    </div>
  );
}