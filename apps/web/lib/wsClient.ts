/**
 * WebSocket 客户端：自动重连 + 心跳 + 订阅管理 + 事件分发。
 *
 * 协议：
 * - 客户端发送：{ action: "subscribe"|"unsubscribe"|"ping", channel: string }
 * - 服务端推送：{ channel: string, type: string, data: any, timestamp: string }
 *
 * 使用：
 *   const ws = getWsClient();
 *   ws.subscribe('system', (msg) => console.log(msg));
 *   ws.connect();
 */
type MessageHandler = (msg: WSMessage) => void;

export interface WSMessage {
  channel: string;
  type: string;
  data: any;
  timestamp: string;
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000, 30000];
const PING_INTERVAL_MS = 30_000;

class WsClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private subscriptions: Map<string, Set<MessageHandler>> = new Map();
  // 暂存待订阅频道（连接建立后自动订阅）
  private pendingChannels: Set<string> = new Set();
  private isConnecting = false;
  private isManuallyClosed = false;

  constructor(url: string) {
    this.url = url;
  }

  connect(): void {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }
    this.isConnecting = true;
    this.isManuallyClosed = false;

    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.isConnecting = false;
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.isConnecting = false;
      this.reconnectAttempt = 0;
      this.startPing();
      // 重新订阅所有频道
      this.subscriptions.forEach((_handlers, channel) => {
        this._send({ action: 'subscribe', channel });
      });
      Array.from(this.pendingChannels).forEach((channel) => {
        this._send({ action: 'subscribe', channel });
        this.pendingChannels.delete(channel);
      });
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        this.dispatch(msg);
      } catch {
        // 忽略非 JSON 消息
      }
    };

    this.ws.onclose = () => {
      this.isConnecting = false;
      this.stopPing();
      if (!this.isManuallyClosed) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose 会跟随触发，重连逻辑在 onclose 处理
    };
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPing();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {}
      this.ws = null;
    }
  }

  subscribe(channel: string, handler: MessageHandler): () => void {
    if (!this.subscriptions.has(channel)) {
      this.subscriptions.set(channel, new Set());
    }
    this.subscriptions.get(channel)!.add(handler);

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this._send({ action: 'subscribe', channel });
    } else {
      this.pendingChannels.add(channel);
      this.connect();
    }

    return () => this.unsubscribe(channel, handler);
  }

  unsubscribe(channel: string, handler: MessageHandler): void {
    const handlers = this.subscriptions.get(channel);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscriptions.delete(channel);
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this._send({ action: 'unsubscribe', channel });
        }
      }
    }
  }

  private _send(payload: object): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(payload));
      } catch {}
    }
  }

  private dispatch(msg: WSMessage): void {
    // P1-14: 不再静默丢弃 _meta 消息，处理 error/connected/ping 等类型
    if (msg.channel === '_meta') {
      if (msg.type === 'error') {
        console.error('WS error:', msg.data?.error || msg.data);
      } else if (msg.type === 'ping') {
        // 服务端心跳 ping，回复 pong
        this._send({ action: 'pong' });
      }
      // connected/subscribed/unsubscribed/pong 等确认消息静默处理
      return;
    }
    const handlers = this.subscriptions.get(msg.channel);
    if (handlers) {
      handlers.forEach((h) => {
        try {
          h(msg);
        } catch (e) {
          console.error('WS handler error:', e);
        }
      });
    }
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this._send({ action: 'ping' });
    }, PING_INTERVAL_MS);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectAttempt, RECONNECT_DELAYS.length - 1)];
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

let _instance: WsClient | null = null;

function getWsUrl(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '';
  // 将 http(s):// 转为 ws(s)://
  let wsBase = apiBase;
  if (apiBase.startsWith('https://')) {
    wsBase = apiBase.replace('https://', 'wss://');
  } else if (apiBase.startsWith('http://')) {
    wsBase = apiBase.replace('http://', 'ws://');
  } else {
    // 同源：用当前页面协议
    if (typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsBase = `${proto}//${window.location.host}`;
    }
  }
  return `${wsBase}/api/ws`;
}

export function getWsClient(): WsClient {
  if (!_instance) {
    _instance = new WsClient(getWsUrl());
  }
  return _instance;
}
