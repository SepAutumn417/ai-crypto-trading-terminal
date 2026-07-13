'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type CheckResult, type ConfirmationChallenge, type OrderIntent } from '@/lib/api';
import { SizingCard } from './SizingCard';
import { RiskCard } from './RiskCard';
import { DecisionCard } from './DecisionCard';
import { OrderConfirmModal } from './OrderConfirmModal';
import { useState } from 'react';

const ACTIVE_STATUSES = ['SUBMITTED', 'PARTIALLY_FILLED'];

export function PlanDetail({ planId }: { planId: string }) {
  const qc = useQueryClient();
  const [result, setResult] = useState<CheckResult | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationChallenge | null>(null);
  const [intent, setIntent] = useState<OrderIntent | null>(null);
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
  const { data: savedIntents = [] } = useQuery({
    queryKey: ['order-intents', planId],
    queryFn: () => api.listOrderIntents(planId),
  });
  const checkMut = useMutation({
    mutationFn: () => api.checkPlan(planId),
    onSuccess: (r) => {
      setResult(r);
      setConfirmation(r.confirmation ?? null);
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
  const confirmMut = useMutation({
    mutationFn: ({ token, passphrase }: { token: string; passphrase?: string }) =>
      api.confirmPlan(planId, token, passphrase),
    onSuccess: () => executeMut.mutate(),
  });
  const previewMut = useMutation({
    mutationFn: () => api.previewOrder(planId),
    onSuccess: (nextIntent) => {
      setIntent(nextIntent);
      qc.invalidateQueries({ queryKey: ['order-intents', planId] });
    },
  });
  const dryRunMut = useMutation({
    mutationFn: (intentId: string) => api.dryRunOrder(intentId),
    onSuccess: (nextIntent) => {
      setIntent(nextIntent);
      qc.invalidateQueries({ queryKey: ['order-intents', planId] });
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

  if (isLoading || !plan) return <p className="text-gray-500">加载中...</p>;

  // P1-23: canExecute 必须同时满足状态在允许集合内 AND decision=ALLOW_CONFIRM，避免 SUBMITTED 误显示
  const canExecute = ['READY_FOR_CONFIRMATION', 'FAILED'].includes(plan.status)
    && result?.decision.result === 'ALLOW_CONFIRM'
    && !!confirmation;
  // P1-24: result 为 null 但状态允许时，点击按钮自动触发检查
  const needsCheck = ['READY_FOR_CONFIRMATION', 'FAILED'].includes(plan.status) && !result;
  const canSync = !!plan.exchange_order_id && ACTIVE_STATUSES.includes(plan.status);
  const canCancel = !!plan.exchange_order_id && ACTIVE_STATUSES.includes(plan.status);
  const intents = intent
    ? [intent, ...savedIntents.filter((savedIntent) => savedIntent.id !== intent.id)]
    : savedIntents;

  const handleExecute = () => {
    // P1-24: result 存在且 decision 允许时打开确认弹窗；result 为 null 时自动触发检查
    if (canExecute) {
      setShowConfirm(true);
    } else if (needsCheck) {
      checkMut.mutate();
    }
  };

  const handleConfirm = (passphrase?: string) => {
    if (!confirmation) return;
    confirmMut.mutate({ token: confirmation.token, passphrase });
  };

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
            <div className="col-span-2 p-3 bg-red-900/30 border border-red-700 rounded text-red-300">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-bold">执行失败</span>
                {plan.execution_error_code && (
                  <span className="text-xs px-2 py-0.5 bg-red-800 rounded">{plan.execution_error_code}</span>
                )}
                {plan.execution_retryable && (
                  <span className="text-xs px-2 py-0.5 bg-yellow-800 rounded text-yellow-200">可重试</span>
                )}
              </div>
              <div className="text-sm">{plan.execution_error}</div>
              {plan.execution_attempts > 0 && (
                <div className="text-xs text-gray-400 mt-1">尝试次数: {plan.execution_attempts}</div>
              )}
            </div>
          )}
        </div>
        {plan.exchange_order_id && (
          <div className="mt-2 text-xs text-gray-500">
            订单ID: {plan.exchange_order_id}
          </div>
        )}
        <div className="mt-4 flex gap-3 flex-wrap">
          {result?.decision.result === 'ALLOW_CONFIRM' && (
            <button onClick={() => previewMut.mutate()} disabled={previewMut.isPending}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-700 px-4 py-2 rounded">
              {previewMut.isPending ? '生成中...' : '订单预览'}
            </button>
          )}
          {(plan.status === 'DRAFT' || plan.status === 'CHECKED' || plan.status === 'READY_FOR_CONFIRMATION') && (
            <button onClick={() => checkMut.mutate()} disabled={checkMut.isPending}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-700 px-4 py-2 rounded">
              {checkMut.isPending ? '检查中...' : '运行检查'}
            </button>
          )}
          {(plan.status === 'READY_FOR_CONFIRMATION' || plan.status === 'FAILED') && (
            <button
              onClick={handleExecute}
              disabled={(canExecute && executeMut.isPending) || checkMut.isPending}
              className={`px-4 py-2 rounded ${
                canExecute && !executeMut.isPending
                  ? plan.status === 'FAILED'
                    ? 'bg-orange-600 hover:bg-orange-700'
                    : 'bg-blue-600 hover:bg-blue-700'
                  : 'bg-gray-700 hover:bg-gray-600'
              }`}
            >
              {executeMut.isPending ? '提交中...' : checkMut.isPending ? '检查中...' : canExecute ? (plan.status === 'FAILED' ? '重试执行' : '执行交易') : '运行检查'}
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
      {intents.length > 0 && (
        <section className="rounded border border-indigo-800 bg-indigo-950/20 p-4 space-y-3">
          <h3 className="font-semibold">订单预览 / Dry Run 历史</h3>
          {intents.map((savedIntent) => (
            <div key={savedIntent.id} className="border-t border-indigo-900 pt-3 first:border-t-0 first:pt-0">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <span>数量：{savedIntent.quantity}</span><span>价格：{savedIntent.entry_price}</span>
                <span>止损：{savedIntent.stop_loss_price ?? '-'}</span><span>状态：{savedIntent.status}</span>
              </div>
              <div className="mt-2 flex items-center gap-3">
                <button onClick={() => dryRunMut.mutate(savedIntent.id)} disabled={dryRunMut.isPending || savedIntent.status === 'DRY_RUN_PASSED'}
                  className="rounded bg-indigo-600 px-4 py-2 disabled:bg-gray-700">
                  {dryRunMut.isPending ? '校验中...' : savedIntent.status === 'DRY_RUN_PASSED' ? 'Dry Run 已通过' : '运行 Dry Run'}
                </button>
                <span className="text-xs text-gray-500">{savedIntent.client_order_id}</span>
              </div>
              {savedIntent.logs.map((log) => <p key={`${log.event_type}-${log.created_at}`} className="mt-1 text-xs text-gray-400">{log.event_type}: {log.message}</p>)}
            </div>
          ))}
        </section>
      )}

      <OrderConfirmModal
        isOpen={showConfirm}
        onClose={() => setShowConfirm(false)}
        onConfirm={handleConfirm}
        result={result}
        plan={plan}
        isSubmitting={confirmMut.isPending || executeMut.isPending}
        errorMessage={executeMut.isError ? (executeMut.error as Error)?.message || '执行失败' : null}
      />
    </div>
  );
}
