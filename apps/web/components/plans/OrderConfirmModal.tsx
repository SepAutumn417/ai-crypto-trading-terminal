'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import type { CheckResult, TradePlan } from '@/lib/api';

interface OrderConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  result: CheckResult | null;
  plan?: TradePlan | null;
  isSubmitting?: boolean;
  errorMessage?: string | null;
}

const COUNTDOWN_SECONDS = 30;
const HIGH_RISK_LEVERAGE = 20;

export function OrderConfirmModal({
  isOpen, onClose, onConfirm, result, plan, isSubmitting, errorMessage,
}: OrderConfirmModalProps) {
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [expired, setExpired] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [showConfirmInput, setShowConfirmInput] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const confirmInputRef = useRef<HTMLInputElement>(null);

  // 判断是否高风险（杠杆 >= 20x 或 risk_percent >= 5%）
  const isHighRisk = (() => {
    if (!result) return false;
    const leverage = parseFloat(plan?.leverage || '0');
    const riskPercent = parseFloat(plan?.risk_percent || '0');
    return leverage >= HIGH_RISK_LEVERAGE || riskPercent >= 5;
  })();

  // 倒计时
  useEffect(() => {
    if (!isOpen || isSubmitting) return;
    setCountdown(COUNTDOWN_SECONDS);
    setExpired(false);
    setConfirmText('');
    setShowConfirmInput(false);

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          setExpired(true);
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, isSubmitting]);

  // Escape 关闭
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isSubmitting) {
        onClose();
      }
      // 简单焦点陷阱：Tab 在模态框内循环
      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    // 初始聚焦到模态框
    setTimeout(() => modalRef.current?.focus(), 0);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isSubmitting, onClose]);

  // 高风险时自动聚焦到确认输入框
  useEffect(() => {
    if (showConfirmInput && confirmInputRef.current) {
      confirmInputRef.current.focus();
    }
  }, [showConfirmInput]);

  const handleConfirmClick = useCallback(() => {
    if (isHighRisk && !showConfirmInput) {
      setShowConfirmInput(true);
      return;
    }
    if (isHighRisk && confirmText !== 'CONFIRM') return;
    onConfirm();
  }, [isHighRisk, showConfirmInput, confirmText, onConfirm]);

  if (!isOpen || !result) return null;

  const { sizing, risk, decision } = result;

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

  const canExecute = decision.result === 'ALLOW_CONFIRM' && !expired && !isSubmitting;
  const countdownColor = countdown <= 5 ? 'text-red-400' : countdown <= 10 ? 'text-yellow-400' : 'text-gray-400';

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="order-confirm-title"
    >
      <div
        ref={modalRef}
        tabIndex={-1}
        className="bg-gray-900 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto outline-none"
      >
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <h2 id="order-confirm-title" className="text-xl font-bold">确认订单</h2>
            <button
              onClick={onClose}
              disabled={isSubmitting}
              aria-label="关闭"
              className="text-gray-400 hover:text-white disabled:opacity-50"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {/* 倒计时 */}
          {!expired && !isSubmitting && (
            <div className={`text-sm mt-2 ${countdownColor}`} role="timer" aria-live="polite">
              ⏱ 确认倒计时：{countdown} 秒（超时自动关闭）
            </div>
          )}
          {expired && (
            <div className="text-sm mt-2 text-red-400" role="alert">
              ⚠ 确认已超时，请重新检查计划
            </div>
          )}
        </div>

        <div className="p-6 space-y-6">
          {/* 失败回退 UI */}
          {errorMessage && (
            <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-4" role="alert">
              <h3 className="font-semibold text-red-400 mb-2">⚠ 执行失败</h3>
              <p className="text-sm text-red-200 break-all">{errorMessage}</p>
              <p className="text-xs text-red-300 mt-2">请检查错误信息，调整后可重新执行</p>
            </div>
          )}

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

          {isHighRisk && decision.result === 'ALLOW_CONFIRM' && (
            <div className="bg-orange-900/30 border border-orange-500/50 rounded-lg p-4">
              <h3 className="font-semibold text-orange-400 mb-2">⚠ 高风险交易</h3>
              <p className="text-sm text-orange-200">
                杠杆 ≥ {HIGH_RISK_LEVERAGE}x 或风险比例 ≥ 5%，需二次确认。
                {showConfirmInput
                  ? ' 请输入 CONFIRM 确认执行：'
                  : ' 点击"确认下单"后需输入确认文本。'}
              </p>
              {showConfirmInput && (
                <input
                  ref={confirmInputRef}
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder="输入 CONFIRM"
                  className="block w-full mt-2 bg-gray-900 border border-orange-500/50 px-3 py-2 rounded text-white"
                  aria-label="输入 CONFIRM 确认"
                />
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-gray-400 text-sm">交易对</div>
              <div className="text-lg font-semibold">{result.plan.symbol}</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">方向</div>
              <div className={`text-lg font-semibold ${
                result.plan.direction === 'LONG' ? 'text-green-400' : 'text-red-400'
              }`}>
                {result.plan.direction === 'LONG' ? '做多' : '做空'}
              </div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">入场价格</div>
              <div className="text-lg font-semibold">{formatNumber(result.plan.entry_price)} USDT</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">止损价格</div>
              <div className="text-lg font-semibold">{formatNumber(result.plan.stop_loss_price)} USDT</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">杠杆</div>
              <div className="text-lg font-semibold">{result.plan.leverage}x</div>
            </div>
            <div>
              <div className="text-gray-400 text-sm">保证金模式</div>
              <div className="text-lg font-semibold">{result.plan.margin_mode === 'isolated' ? '逐仓' : '全仓'}</div>
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
            {expired ? '关闭' : '取消'}
          </button>
          <button
            onClick={handleConfirmClick}
            disabled={!canExecute || (isHighRisk && showConfirmInput && confirmText !== 'CONFIRM')}
            className={`flex-1 px-4 py-2.5 rounded font-medium transition-colors ${
              canExecute && !(isHighRisk && showConfirmInput && confirmText !== 'CONFIRM')
                ? 'bg-green-600 hover:bg-green-700'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            }`}
            aria-disabled={!canExecute}
          >
            {isSubmitting
              ? '提交中...'
              : expired
              ? '已超时'
              : isHighRisk && !showConfirmInput
              ? '确认下单（需二次确认）'
              : isHighRisk && confirmText !== 'CONFIRM'
              ? '请输入 CONFIRM'
              : canExecute
              ? '确认下单'
              : '无法执行'}
          </button>
        </div>
      </div>
    </div>
  );
}
