'use client';
import { TradeJournal } from '@/lib/api';

interface JournalDetailProps {
  journal: TradeJournal | null;
}

export function JournalDetail({ journal }: JournalDetailProps) {
  if (!journal) {
    return (
      <div className="text-gray-500 text-center py-12 bg-gray-900 rounded-lg">
        选择一笔交易查看详情
      </div>
    );
  }

  const formatPrice = (price: string | null) => {
    if (!price) return '-';
    return parseFloat(price).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatPnl = (pnl: string | null) => {
    if (!pnl) return '-';
    const num = parseFloat(pnl);
    const prefix = num >= 0 ? '+' : '';
    return `${prefix}${num.toFixed(2)} USDT`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-xl font-bold">{journal.symbol}</h3>
          <span className={`px-2 py-1 rounded text-sm ${
            journal.direction === 'LONG'
              ? 'bg-green-900/50 text-green-400'
              : 'bg-red-900/50 text-red-400'
          }`}>
            {journal.direction === 'LONG' ? '做多' : '做空'}
          </span>
          <span className={`px-2 py-1 rounded text-sm ${
            journal.status === 'OPEN'
              ? 'bg-yellow-900/50 text-yellow-400'
              : 'bg-gray-700 text-gray-300'
          }`}>
            {journal.status === 'OPEN' ? '进行中' : '已平仓'}
          </span>
        </div>
        {journal.pnl && (
          <div className={`text-xl font-bold ${
            parseFloat(journal.pnl) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatPnl(journal.pnl)}
            {journal.pnl_percent && (
              <span className="text-sm ml-2">
                ({parseFloat(journal.pnl_percent) >= 0 ? '+' : ''}
                {parseFloat(journal.pnl_percent).toFixed(2)}%)
              </span>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <div className="text-gray-400 text-sm">入场价格</div>
          <div className="text-lg font-semibold">{formatPrice(journal.entry_price)}</div>
        </div>
        <div>
          <div className="text-gray-400 text-sm">出场价格</div>
          <div className="text-lg font-semibold">{formatPrice(journal.exit_price)}</div>
        </div>
        <div>
          <div className="text-gray-400 text-sm">数量</div>
          <div className="text-lg font-semibold">{journal.quantity}</div>
        </div>
        <div>
          <div className="text-gray-400 text-sm">杠杆</div>
          <div className="text-lg font-semibold">{journal.leverage}x</div>
        </div>
      </div>

      {journal.setup_type && (
        <div>
          <div className="text-gray-400 text-sm mb-1">形态类型</div>
          <div>{journal.setup_type}</div>
        </div>
      )}

      {journal.entry_reason && (
        <div>
          <div className="text-gray-400 text-sm mb-1">入场理由</div>
          <div className="bg-gray-800 rounded p-3">{journal.entry_reason}</div>
        </div>
      )}

      {journal.exit_reason && (
        <div>
          <div className="text-gray-400 text-sm mb-1">出场理由</div>
          <div className="bg-gray-800 rounded p-3">{journal.exit_reason}</div>
        </div>
      )}

      {journal.lessons_learned && (
        <div>
          <div className="text-gray-400 text-sm mb-1">经验教训</div>
          <div className="bg-gray-800 rounded p-3">{journal.lessons_learned}</div>
        </div>
      )}

      {journal.emotions && (
        <div>
          <div className="text-gray-400 text-sm mb-1">情绪状态</div>
          <div>{journal.emotions}</div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-400">入场时间</div>
          <div>{formatDate(journal.entry_at || journal.created_at)}</div>
        </div>
        <div>
          <div className="text-gray-400">出场时间</div>
          <div>{formatDate(journal.exit_at)}</div>
        </div>
      </div>
    </div>
  );
}
