'use client';
import { TradeJournalSummary } from '@/lib/api';

interface JournalSummaryProps {
  data: TradeJournalSummary | null;
}

export function JournalSummary({ data }: JournalSummaryProps) {
  if (!data) {
    return <div className="text-gray-500 text-center py-4">加载中...</div>;
  }

  const formatPnl = (pnl: string | null) => {
    if (!pnl) return '-';
    const num = parseFloat(pnl);
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${num.toFixed(2)} USDT`;
  };

  const formatPercent = (pct: string | null) => {
    if (!pct) return '-';
    return `${parseFloat(pct).toFixed(2)}%`;
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-gray-900 rounded-lg p-4">
        <div className="text-gray-400 text-sm">总交易数</div>
        <div className="text-2xl font-bold mt-1">{data.total_trades}</div>
        <div className="text-sm mt-1">
          <span className="text-green-400">胜 {data.winning_trades}</span>
          <span className="text-gray-500 mx-2">/</span>
          <span className="text-red-400">负 {data.losing_trades}</span>
        </div>
      </div>

      <div className="bg-gray-900 rounded-lg p-4">
        <div className="text-gray-400 text-sm">胜率</div>
        <div className="text-2xl font-bold mt-1">
          {data.win_rate ? formatPercent(data.win_rate) : '-'}
        </div>
      </div>

      <div className="bg-gray-900 rounded-lg p-4">
        <div className="text-gray-400 text-sm">总盈亏</div>
        <div className={`text-2xl font-bold mt-1 ${
          parseFloat(data.total_pnl) >= 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {formatPnl(data.total_pnl)}
        </div>
      </div>

      <div className="bg-gray-900 rounded-lg p-4">
        <div className="text-gray-400 text-sm">平均盈亏</div>
        <div className={`text-2xl font-bold mt-1 ${
          data.avg_pnl && parseFloat(data.avg_pnl) >= 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {formatPnl(data.avg_pnl)}
        </div>
      </div>
    </div>
  );
}
