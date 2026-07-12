'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, KlineInterval } from '@/lib/api';
import { AIScoreCard } from '@/components/ai/AIScoreCard';
import { SignalList } from '@/components/ai/SignalList';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const INTERVALS: { label: string; value: KlineInterval }[] = [
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '4h', value: '4h' },
  { label: '1d', value: '1d' },
];

export default function AIPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG');
  const [entryPrice, setEntryPrice] = useState('65000');
  const [interval, setInterval] = useState<KlineInterval>('1h');

  const { data: evaluation, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['ai-evaluate', symbol, direction, entryPrice, interval],
    queryFn: () => api.evaluateOpportunity({
      symbol,
      direction,
      entry_price: entryPrice,
      interval,
      limit: 100,
    }),
    enabled: false,
  });

  const handleEvaluate = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">技术指标评分</h1>
      <p className="text-sm text-gray-500">
        基于 RSI、MACD、布林带、均线和成交量的固定规则加权评分，非 AI 模型预测。
        评分仅作为参考，不构成交易建议。
      </p>

      {isError && (
        <p className="text-red-400 text-sm">评估失败：{(error as Error).message}</p>
      )}

      <div className="bg-gray-900 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">交易设置</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">交易对</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2"
            >
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">方向</label>
            <div className="flex gap-2">
              <button
                onClick={() => setDirection('LONG')}
                className={`flex-1 py-2 rounded font-medium transition-colors ${
                  direction === 'LONG'
                    ? 'bg-green-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                做多
              </button>
              <button
                onClick={() => setDirection('SHORT')}
                className={`flex-1 py-2 rounded font-medium transition-colors ${
                  direction === 'SHORT'
                    ? 'bg-red-600 text-white'
                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                }`}
              >
                做空
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">入场价格</label>
            <input
              type="number"
              value={entryPrice}
              onChange={(e) => setEntryPrice(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2"
              placeholder="输入入场价格"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">时间周期</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value as KlineInterval)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2"
            >
              {INTERVALS.map((i) => (
                <option key={i.value} value={i.value}>{i.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6">
          <button
            onClick={handleEvaluate}
            disabled={isLoading || !entryPrice}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded font-medium transition-colors"
          >
            {isLoading ? '评估中...' : '开始评估'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <h2 className="text-lg font-semibold mb-4">综合评分</h2>
          <AIScoreCard data={evaluation || null} loading={isLoading} />
        </div>
        <div className="lg:col-span-2">
          <h2 className="text-lg font-semibold mb-4">指标分析</h2>
          <div className="bg-gray-900 rounded-lg p-4">
            {evaluation ? (
              <SignalList signals={evaluation.signals} />
            ) : (
              <div className="text-gray-500 text-center py-8">
                点击「开始评估」查看详细指标分析
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
