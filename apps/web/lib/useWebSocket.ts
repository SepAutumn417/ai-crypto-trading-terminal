/**
 * WebSocket React Hook：集成 React Query invalidation。
 *
 * 当收到指定频道的消息时，自动 invalidate 对应的 query keys，
 * 触发相关组件重新获取数据，实现实时更新。
 *
 * 使用：
 *   useWebSocketInvalidation('system', ['systemStatus']);
 *   useWebSocketInvalidation('plans', ['plans', 'plan']);
 *   useWebSocketInvalidation('journals', ['journals', 'journalSummary']);
 */
'use client';
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getWsClient, type WSMessage } from './wsClient';

interface Invalidator {
  queryKeys: string[];
  // 可选：自定义处理消息（如直接更新 cache）
  onMessage?: (msg: WSMessage, qc: ReturnType<typeof useQueryClient>) => void;
}

/**
 * 订阅频道，收到消息时 invalidate 指定 query keys。
 */
export function useWebSocketInvalidation(
  channel: string,
  queryKeys: string[],
  onMessage?: (msg: WSMessage) => void,
): void {
  const qc = useQueryClient();

  useEffect(() => {
    const ws = getWsClient();
    const unsub = ws.subscribe(channel, (msg) => {
      if (onMessage) {
        onMessage(msg);
      }
      queryKeys.forEach((key) => {
        qc.invalidateQueries({ queryKey: [key] });
      });
    });
    return () => {
      unsub();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel]);
}

/**
 * 订阅 ticker.{symbol} 频道，收到行情更新时调用回调。
 */
export function useTickerWebSocket(
  symbol: string | null,
  onTicker: (data: { symbol: string; last_price: string; mark_price?: string; timestamp?: string }) => void,
): void {
  useEffect(() => {
    if (!symbol) return;
    const ws = getWsClient();
    const channel = `ticker.${symbol}`;
    const unsub = ws.subscribe(channel, (msg) => {
      if (msg.type === 'ticker_update' && msg.data) {
        onTicker(msg.data);
      }
    });
    return () => {
      unsub();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);
}
