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
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getWsClient, type WSMessage } from './wsClient';

/**
 * 订阅频道，收到消息时 invalidate 指定 query keys。
 *
 * P1-30: 用 useRef 保存最新的 queryKeys / onMessage，避免闭包陈旧导致
 * 父组件传入动态值时订阅持有旧引用。
 */
export function useWebSocketInvalidation(
  channel: string,
  queryKeys: string[],
  onMessage?: (msg: WSMessage) => void,
): void {
  const qc = useQueryClient();
  const queryKeysRef = useRef(queryKeys);
  const onMessageRef = useRef(onMessage);
  queryKeysRef.current = queryKeys;
  onMessageRef.current = onMessage;

  useEffect(() => {
    const ws = getWsClient();
    const unsub = ws.subscribe(channel, (msg) => {
      if (onMessageRef.current) {
        onMessageRef.current(msg);
      }
      queryKeysRef.current.forEach((key) => {
        qc.invalidateQueries({ queryKey: [key] });
      });
    });
    return () => {
      unsub();
    };
  }, [channel, qc]);
}

/**
 * 订阅 ticker.{symbol} 频道，收到行情更新时调用回调。
 *
 * P1-30: 用 useRef 保存最新的 onTicker，避免闭包陈旧。
 */
export function useTickerWebSocket(
  symbol: string | null,
  onTicker: (data: { symbol: string; last_price: string; mark_price?: string; timestamp?: string }) => void,
): void {
  const onTickerRef = useRef(onTicker);
  onTickerRef.current = onTicker;

  useEffect(() => {
    if (!symbol) return;
    const ws = getWsClient();
    const channel = `ticker.${symbol}`;
    const unsub = ws.subscribe(channel, (msg) => {
      if (msg.type === 'ticker_update' && msg.data) {
        onTickerRef.current(msg.data);
      }
    });
    return () => {
      unsub();
    };
  }, [symbol]);
}
