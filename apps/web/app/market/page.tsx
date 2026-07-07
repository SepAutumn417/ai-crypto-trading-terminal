'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, KlineInterval } from '@/lib/api';
import { KlineChart } from '@/components/market/KlineChart';
import { Orderbook } from '@/components/market/Orderbook';
import { TickerInfo } from '@/components/market/TickerInfo';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const INTERVALS: { label: string; value: KlineInterval }[] = [
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '4h', value: '4h' },
  { label: '1d', value: '1d' },
];

export default function MarketPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [interval, setInterval] = useState<KlineInterval>('1h');

  const { data: ticker } = useQuery({
    queryKey: ['ticker', symbol],
    queryFn: () => api.getTicker(symbol),
    refetchInterval: 5000,
  });

  const { data: klines = [] } = useQuery({
    queryKey: ['klines', symbol, interval],
    queryFn: () => api.getKlines(symbol, interval, 100),
  });

  const { data: orderbook } = useQuery({
    queryKey: ['orderbook', symbol],
    queryFn: () => api.getOrderbook(symbol, 20),
    refetchInterval: 2000,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex gap-2">
          {SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                symbol === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2 ml-auto">
          {INTERVALS.map((i) => (
            <button
              key={i.value}
              onClick={() => setInterval(i.value)}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                interval === i.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {i.label}
            </button>
          ))}
        </div>
      </div>

      <TickerInfo data={ticker || null} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="bg-gray-900 rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-3">K 线图</h3>
            <KlineChart data={klines} height={450} />
          </div>
        </div>
        <div>
          <Orderbook data={orderbook || null} />
        </div>
      </div>
    </div>
  );
}
