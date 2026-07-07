'use client';
import { Ticker } from '@/lib/api';

interface TickerInfoProps {
  data: Ticker | null;
}

export function TickerInfo({ data }: TickerInfoProps) {
  if (!data) {
    return <div className="text-gray-500 text-center py-4">加载中...</div>;
  }

  const change = data.change_percent_24h ? parseFloat(data.change_percent_24h) : 0;
  const isPositive = change >= 0;

  const formatPrice = (price: string | null) => {
    if (!price) return '-';
    const num = parseFloat(price);
    return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatVolume = (vol: string | null) => {
    if (!vol) return '-';
    const num = parseFloat(vol);
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toFixed(2);
  };

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex items-baseline gap-4 mb-4">
        <h2 className="text-2xl font-bold">{data.symbol}</h2>
        <span className={`text-2xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {formatPrice(data.last_price)}
        </span>
        <span className={`text-sm ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {isPositive ? '+' : ''}{change.toFixed(2)}%
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div>
          <div className="text-gray-400">24h 最高</div>
          <div className="text-green-400">{formatPrice(data.high_24h)}</div>
        </div>
        <div>
          <div className="text-gray-400">24h 最低</div>
          <div className="text-red-400">{formatPrice(data.low_24h)}</div>
        </div>
        <div>
          <div className="text-gray-400">24h 成交量</div>
          <div>{formatVolume(data.volume_24h)}</div>
        </div>
        <div>
          <div className="text-gray-400">标记价格</div>
          <div>{formatPrice(data.mark_price)}</div>
        </div>
      </div>
    </div>
  );
}
