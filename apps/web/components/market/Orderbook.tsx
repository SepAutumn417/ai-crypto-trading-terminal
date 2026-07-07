'use client';
import { Orderbook as OrderbookType } from '@/lib/api';

interface OrderbookProps {
  data: OrderbookType | null;
}

export function Orderbook({ data }: OrderbookProps) {
  if (!data) {
    return <div className="text-gray-500 text-center py-8">加载中...</div>;
  }

  const maxQty = Math.max(
    ...data.bids.map(b => parseFloat(b.quantity)),
    ...data.asks.map(a => parseFloat(a.quantity)),
    1
  );

  const formatPrice = (price: string) => {
    const num = parseFloat(price);
    return num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const formatQty = (qty: string) => {
    const num = parseFloat(qty);
    return num.toFixed(4);
  };

  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <h3 className="text-lg font-semibold mb-3">订单簿</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-sm text-gray-400 mb-2 grid grid-cols-2">
            <span>价格(USDT)</span>
            <span className="text-right">数量</span>
          </div>
          <div className="space-y-0.5">
            {data.bids.map((bid, i) => {
              const pct = (parseFloat(bid.quantity) / maxQty) * 100;
              return (
                <div key={i} className="relative grid grid-cols-2 text-sm py-0.5">
                  <div
                    className="absolute inset-y-0 left-0 bg-green-500 opacity-20"
                    style={{ width: `${pct}%` }}
                  />
                  <span className="relative text-green-400">{formatPrice(bid.price)}</span>
                  <span className="relative text-right">{formatQty(bid.quantity)}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="text-sm text-gray-400 mb-2 grid grid-cols-2">
            <span>价格(USDT)</span>
            <span className="text-right">数量</span>
          </div>
          <div className="space-y-0.5">
            {data.asks.map((ask, i) => {
              const pct = (parseFloat(ask.quantity) / maxQty) * 100;
              return (
                <div key={i} className="relative grid grid-cols-2 text-sm py-0.5">
                  <div
                    className="absolute inset-y-0 right-0 bg-red-500 opacity-20"
                    style={{ width: `${pct}%` }}
                  />
                  <span className="relative text-red-400">{formatPrice(ask.price)}</span>
                  <span className="relative text-right">{formatQty(ask.quantity)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
