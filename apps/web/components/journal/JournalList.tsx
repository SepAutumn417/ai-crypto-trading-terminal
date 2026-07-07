'use client';
import { TradeJournal } from '@/lib/api';

interface JournalListProps {
  items: TradeJournal[];
  onSelect: (id: string) => void;
  selectedId: string | null;
}

export function JournalList({ items, onSelect, selectedId }: JournalListProps) {
  const formatPrice = (price: string) => {
    return parseFloat(price).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatPnl = (pnl: string | null) => {
    if (!pnl) return '-';
    const num = parseFloat(pnl);
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${num.toFixed(2)}`;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (items.length === 0) {
    return (
      <div className="text-gray-500 text-center py-8 bg-gray-900 rounded-lg">
        暂无交易记录
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((journal) => (
        <div
          key={journal.id}
          onClick={() => onSelect(journal.id)}
          className={`p-4 rounded-lg cursor-pointer transition-colors ${
            selectedId === journal.id
              ? 'bg-blue-900/50 border border-blue-500'
              : 'bg-gray-900 hover:bg-gray-800 border border-transparent'
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold">{journal.symbol}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                journal.direction === 'LONG'
                  ? 'bg-green-900/50 text-green-400'
                  : 'bg-red-900/50 text-red-400'
              }`}>
                {journal.direction === 'LONG' ? '多' : '空'}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                journal.status === 'OPEN'
                  ? 'bg-yellow-900/50 text-yellow-400'
                  : 'bg-gray-700 text-gray-300'
              }`}>
                {journal.status === 'OPEN' ? '进行中' : '已平仓'}
              </span>
            </div>
            {journal.pnl && (
              <span className={`font-bold ${
                parseFloat(journal.pnl) >= 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {formatPnl(journal.pnl)}
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 text-sm text-gray-400">
            <div>
              入场: <span className="text-white">{formatPrice(journal.entry_price)}</span>
            </div>
            <div>
              出场: <span className="text-white">
                {journal.exit_price ? formatPrice(journal.exit_price) : '-'}
              </span>
            </div>
            <div className="text-right">
              {formatDate(journal.created_at)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
