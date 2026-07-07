'use client';
import { CheckResult } from '@/lib/api';

interface OrderConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  result: CheckResult | null;
  isSubmitting?: boolean;
}

export function OrderConfirmModal({ isOpen, onClose, onConfirm, result, isSubmitting }: OrderConfirmModalProps) {
  if (!isOpen || !result) return null;

  const { plan, sizing, risk, decision } = result;

  const formatNumber = (num: string | null | undefined, decimals = 2) => {
    if (!num) return '-';
    return parseFloat(num).toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const decisionColors: Record<string, string> = {
    ALLOW_CONFIRM: 'bg-green-900/50 text-green-400 border-green-500/30',
    WAIT: 'bg-yellow-900/50 text-yellow-400 border-yellow-500/30',
    REDUCE_RISK: 'bg-orange-900/50 text-orange-400 border-orange-500/30',
    BLOCK: 'bg-red-900/50 text-red-400 border-red-500/30',
    EXPIRED: 'bg-gray-900/50 text-gray-400 border-gray-500/30',
  };

  const decisionLabels: Record<string, string> = {
    ALLOW_CONFIRM: '允许执行',
    WAIT: '等待确认',
    REDUCE_RISK: '建议降低仓位',
    BLOCK: '禁止执行',
    EXPIRED: '已过期',
  };

  const canExecute = decision.result === 'ALLOW_CONFIRM';

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">确认订单</h2>
            <button
              onClick={onClose}
              disabled={isSubmitting}
              className="text-gray-400 hover:text-white disabled:opacity-50"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="p-6 space-y-6">
          <div className={`p-4 rounded-lg border ${decisionColors[decision.result] || decisionColors.WAIT}`}>
            <div className="flex items-center justify-between">
              <span className="font-semibold">决策结果</span>
              <span className="font-bold">{decisionLabels[decision.result] || decision.result}</span>
            </div>
            {decision.reasons.length > 0 && (
              <ul className="mt-2 text-sm space-y-1">
                {decision.reasons.map((reason, i) => (
                  <li key={i}>• {reason}</li>
                ))}
              </ul>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-gray-400 text-sm">交易对</div>
              <div className="text-lg font-semibold">{plan.symbol}</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">方向</div>
              <div className={`text-lg font-semibold ${
                plan.direction === 'LONG' ? 'text-green-400' : 'text-red-400'
              }`}>
                {plan.direction === 'LONG' ? '做多' : '做空'}
              </div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">入场价格</div>
              <div className="text-lg font-semibold">{formatNumber(plan.entry_price)} USDT</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">止损价格</div>
              <div className="text-lg font-semibold">{formatNumber(plan.stop_loss_price)} USDT</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">杠杆</div>
              <div className="text-lg font-semibold">{plan.leverage}x</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">保证金模式</div>
              <div className="text-lg font-semibold">{plan.margin_mode === 'isolated' ? '逐仓' : '全仓'}</div>
            </div>
          </div>

          <div className="bg-gray-800/50 rounded-lg p-4">
            <h3 className="font-semibold mb-3">仓位计算</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-400">账户权益：</span>
                <span>{formatNumber(sizing.equity)} USDT</span>
              </div>
              <div>
                <span className="text-gray-400">风险比例：</span>
                <span>{formatNumber(sizing.risk_percent)}%</span>
              </div>
              <div>
                <span className="text-gray-400">风险金额：</span>
                <span>{formatNumber(sizing.risk_amount)} USDT</span>
              </div>
              <div>
                <span className="text-gray-400">开仓数量：</span>
                <span className="font-semibold">{sizing.rounded_size || sizing.raw_size}</span>
              </div>
              <div>
                <span className="text-gray-400">名义价值：</span>
                <span>{formatNumber(sizing.notional_value)} USDT</span>
              </div>
              <div>
                <span className="text-gray-400">所需保证金：</span>
                <span>{formatNumber(sizing.required_margin)} USDT</span>
              </div>
              <div>
                <span className="text-gray-400">盈亏比：</span>
                <span>{formatNumber(sizing.risk_reward_ratio, 2)}</span>
              </div>
              <div>
                <span className="text-gray-400">预估费用：</span>
                <span>{formatNumber(sizing.estimated_fee)} USDT</span>
              </div>
            </div>
            {sizing.sizing_warnings.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-700">
                <div className="text-yellow-400 text-sm">⚠️ 警告：</div>
                <ul className="text-sm text-yellow-300 mt-1 space-y-1">
                  {sizing.sizing_warnings.map((w, i) => (
                    <li key={i}>• {w}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {risk.warnings.length > 0 && (
            <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4">
              <h3 className="font-semibold text-yellow-400 mb-2">风控警告</h3>
              <ul className="text-sm text-yellow-200 space-y-1">
                {risk.warnings.map((w, i) => (
                  <li key={i}>• {w}</li>
                ))}
              </ul>
            </div>
          )}

          {risk.block_reasons.length > 0 && (
            <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
              <h3 className="font-semibold text-red-400 mb-2">禁止原因</h3>
              <ul className="text-sm text-red-200 space-y-1">
                {risk.block_reasons.map((r, i) => (
                  <li key={i}>• {r}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="p-6 border-t border-gray-800 flex gap-3">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="flex-1 px-4 py-2.5 bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded font-medium transition-colors"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            disabled={!canExecute || isSubmitting}
            className={`flex-1 px-4 py-2.5 rounded font-medium transition-colors ${
              canExecute && !isSubmitting
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            }`}
          >
            {isSubmitting ? '提交中...' : canExecute ? '确认下单' : '无法执行'}
          </button>
        </div>
      </div>
    </div>
  );
}
