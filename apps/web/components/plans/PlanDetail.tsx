'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type CheckResult, type TradePlan } from '@/lib/api';
import { SizingCard } from './SizingCard';
import { RiskCard } from './RiskCard';
import { DecisionCard } from './DecisionCard';
import { OrderConfirmModal } from './OrderConfirmModal';
import { useState, useEffect } from 'react';

const ACTIVE_STATUSES = ['SUBMITTED', 'PARTIALLY_FILLED'];

export function PlanDetail({ planId }: { planId: string }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<CheckResult | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const { data: plan, isLoading } = useQuery({
    queryKey: ['plan', planId],
    queryFn: () => api.getPlan(planId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && ACTIVE_STATUSES.includes(data.status)) {
        return 3000;
      }
      return false;
    },
  });
  const checkMut = useMutation({
    mutationFn: () => api.checkPlan(planId),
    onSuccess: (r) => {
      setResult(r);
      qc.invalidateQueries({ queryKey: ['plan', planId] });
      qc.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const executeMut = useMutation({
    mutationFn: () => api.executePlan(planId),
    onSuccess: () => {
      setShowConfirm(false);
      qc.invalidateQueries({ queryKey: ['plan', planId] });
      qc.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const syncMut = useMutation({
    mutationFn: () => api.syncOrderStatus(planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plan', planId] });
      qc.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const cancelMut = useMutation({
    mutationFn: () => api.cancelPlanOrder(planId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plan', planId] });
      qc.invalidateQueries({ queryKey: ['plans'] });
    },
  });

  const handleExecute = () => {
    if (result) {
      setShowConfirm(true);
    }
  };

  const handleConfirm = () => {
    executeMut.mutate();
  };

  useEffect(() => {
    if (plan && result && result.plan.id === plan.id) {
      setResult({ ...result, plan });
    }
  }, [plan, result]);

  if (isLoading || !plan) return <p className="text-gray-500">加载中...</p>;

  const canExecute = plan.status === 'READY_FOR_CONFIRMATION' || result?.decision.result === 'ALLOW_CONFIRM';
  const canSync = !!plan.exchange_order_id && ACTIVE_STATUSES.includes(plan.status);
  const canCancel = !!plan.exchange_order_id && ACTIVE_STATUSES.includes(plan.status);

  const statusColors: Record<string, string> = {
    DRAFT: 'text-gray-400',
    CHECKED: 'text-blue-400',
    READY_FOR_CONFIRMATION: 'text-green-400',
    SUBMITTED: 'text-yellow-400',
    PARTIALLY_FILLED: 'text-orange-400',
    FILLED: 'text-green-400',
    CANCELLED: 'text-gray-400',
    FAILED: 'text-red-400',
    EXPIRED: 'text-gray-500',
  };

  return (
    <div className="space-y-4">
      <div className="p-4 border border-gray-800 rounded">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-bold">{plan.symbol} {plan.direction}</h3>
          <span className={`font-bold ${statusColors[plan.status] || 'text-gray-400'}`}>
            {plan.status}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>入场: {plan.entry_price}</div>
          <div>止损: {plan.stop_loss_price ?? '-'}</div>
          <div>杠杆: {plan.leverage}x</div>
          <div>风险: {plan.risk_percent}%</div>
          <div>等级: {plan.opportunity_grade}</div>
          <div>数量: {plan.filled_quantity ?? '-'}</div>
          {plan.average_fill_price && (
            <div className="col-span-2">成交均价: {plan.average_fill_price}</div>
          )}
          {plan.execution_error && (
            <div className="col-span-2 text-red-400">错误: {plan.execution_error}</div>
          )}
        </div>
        {plan.exchange_order_id && (
          <div className="mt-2 text-xs text-gray-500">
            订单ID: {plan.exchange_order_id}
          </div>
        )}
        <div className="mt-4 flex gap-3 flex-wrap">
          {(plan.status === 'DRAFT' || plan.status === 'CHECKED' || plan.status === 'READY_FOR_CONFIRMATION') && (
            <button onClick={() => checkMut.mutate()} disabled={checkMut.isPending}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 px-4 py-2 rounded">
              {checkMut.isPending ? '检查中...' : '运行检查'}
            </button>
          )}
          {(plan.status === 'READY_FOR_CONFIRMATION' || (result && canExecute)) && (
            <button
              onClick={handleExecute}
              disabled={!canExecute || executeMut.isPending}
              className={`px-4 py-2 rounded ${
                canExecute && !executeMut.isPending
                  ? 'bg-blue-600 hover:bg-blue-700'
                  : 'bg-gray-700 text-gray-500 cursor-not-allowed'
              }`}
            >
              {executeMut.isPending ? '提交中...' : '执行交易'}
            </button>
          )}
          {canSync && (
            <button
              onClick={() => syncMut.mutate()}
              disabled={syncMut.isPending}
              className="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50"
            >
              {syncMut.isPending ? '同步中...' : '同步状态'}
            </button>
          )}
          {canCancel && (
            <button
              onClick={() => cancelMut.mutate()}
              disabled={cancelMut.isPending}
              className="px-4 py-2 rounded bg-red-600 hover:bg-red-700 disabled:opacity-50"
            >
              {cancelMut.isPending ? '取消中...' : '取消订单'}
            </button>
          )}
        </div>
      </div>
      {result && (
        <div className="space-y-3">
          <SizingCard sizing={result.sizing} />
          <RiskCard risk={result.risk} />
          <DecisionCard decision={result.decision} />
        </div>
      )}

      <OrderConfirmModal
        isOpen={showConfirm}
        onClose={() => setShowConfirm(false)}
        onConfirm={handleConfirm}
        result={result}
        isSubmitting={executeMut.isPending}
      />
    </div>
  );
}