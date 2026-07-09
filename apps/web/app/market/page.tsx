'use client';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, KlineInterval } from '@/lib/api';
import { KlineChart } from '@/components/market/KlineChart';
import { Orderbook } from '@/components/market/Orderbook';
import { TickerInfo } from '@/components/market/TickerInfo';
import { StructurePanel } from '@/components/market/StructurePanel';
import { useTickerWebSocket } from '@/lib/useWebSocket';
import type { Ticker } from '@/lib/api';

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

  const { data: ticker, isError: tickerError } = useQuery({
    queryKey: ['ticker', symbol],
    queryFn: () => api.getTicker(symbol),
    // WebSocket 实时推送 ticker，HTTP 仅做初始加载和兜底
    refetchInterval: 30000,
  });

  const { data: klines = [], isError: klinesError, error: klinesErr } = useQuery({
    queryKey: ['klines', symbol, interval],
    queryFn: () => api.getKlines(symbol, interval, 100),
  });

  const { data: orderbook, isError: orderbookError } = useQuery({
    queryKey: ['orderbook', symbol],
    queryFn: () => api.getOrderbook(symbol, 20),
    refetchInterval: 2000,
  });

  // v0.3: 市场结构识别
  const { data: structure, isError: structureError } = useQuery({
    queryKey: ['marketStructure', symbol, interval],
    queryFn: () => api.getMarketStructure(symbol, interval, 200),
    refetchInterval: 30000, // 30s 刷新结构
  });

  // 实时 ticker 推送：用 updater 形式避免闭包陈旧（P1-15）
  const qc = useQueryClient();
  useTickerWebSocket(symbol, (data) => {
    // P1-15: 使用 updater 形式读取 prev，避免闭包捕获过期 ticker
    qc.setQueryData<Ticker>(['ticker', symbol], (prev) => {
      if (!prev) {
        // 首次推送时创建完整对象
        return {
          symbol: data.symbol,
          last_price: data.last_price,
          mark_price: data.mark_price || null,
          index_price: null,
          high_24h: null,
          low_24h: null,
          volume_24h: null,
          change_percent_24h: null,
          timestamp: data.timestamp || null,
        };
      }
      // 只更新 WS 推送的字段，保留 HTTP 已获取的 24h 数据
      return {
        ...prev,
        last_price: data.last_price,
        mark_price: data.mark_price || prev.mark_price,
        timestamp: data.timestamp || prev.timestamp,
      };
    });
  });

  return (
    <div className="space-y-6">
      {tickerError && <p className="text-red-400 text-sm">行情数据加载失败</p>}
      {klinesError && (
        <p className="text-red-400 text-sm">K 线加载失败：{(klinesErr as Error).message}</p>
      )}
      {orderbookError && <p className="text-red-400 text-sm">订单簿加载失败</p>}
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
        <div className="space-y-4">
          <StructurePanel snapshot={structure ?? null} isError={structureError} />
          <Orderbook data={orderbook || null} />
        </div>
      </div>
    </div>
  );
}
