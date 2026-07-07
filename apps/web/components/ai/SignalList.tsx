'use client';
import { AIIndicatorSignal } from '@/lib/api';

interface SignalListProps {
  signals: AIIndicatorSignal[];
}

const signalColors: Record<string, { text: string; bg: string; label: string }> = {
  strong_buy: { text: 'text-green-400', bg: 'bg-green-500/20', label: '强烈看多' },
  buy: { text: 'text-green-300', bg: 'bg-green-500/10', label: '看多' },
  neutral: { text: 'text-gray-400', bg: 'bg-gray-500/10', label: '中性' },
  sell: { text: 'text-red-300', bg: 'bg-red-500/10', label: '看空' },
  strong_sell: { text: 'text-red-400', bg: 'bg-red-500/20', label: '强烈看空' },
};

export function SignalList({ signals }: SignalListProps) {
  if (signals.length === 0) {
    return <div className="text-gray-500 text-center py-4">暂无信号</div>;
  }

  return (
    <div className="space-y-3">
      {signals.map((signal, index) => {
        const color = signalColors[signal.signal] || signalColors.neutral;
        const score = parseFloat(signal.score);

        return (
          <div key={index} className={`p-3 rounded-lg ${color.bg}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-semibold">{signal.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${color.text} border border-current/30`}>
                  {color.label}
                </span>
              </div>
              <div className="text-right">
                <span className={`font-bold ${color.text}`}>{score.toFixed(0)}</span>
                <span className="text-gray-500 text-sm"> / 100</span>
              </div>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-1.5 mb-2">
              <div
                className={`h-1.5 rounded-full ${
                  score >= 60 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
                }`}
                style={{ width: `${score}%` }}
              />
            </div>
            {signal.value && (
              <div className="text-sm text-gray-400 mb-1">数值: {signal.value}</div>
            )}
            <div className="text-sm text-gray-300">{signal.explanation}</div>
          </div>
        );
      })}
    </div>
  );
}
