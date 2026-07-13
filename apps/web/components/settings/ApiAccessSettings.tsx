'use client';

import { useEffect, useState } from 'react';
import { clearApiToken, clearWsToken, getApiToken, getWsToken, setApiToken, setWsToken } from '@/lib/api';

/** Runtime-only API access configuration for a single-user local terminal. */
export function ApiAccessSettings() {
  const [token, setToken] = useState('');
  const [wsToken, setWsTokenValue] = useState('');

  useEffect(() => {
    setToken(getApiToken() ?? '');
    setWsTokenValue(getWsToken() ?? '');
  }, []);

  const save = () => {
    if (!token.trim()) return;
    setApiToken(token);
    setWsToken(wsToken);
    window.location.reload();
  };

  const clear = () => {
    clearApiToken();
    clearWsToken();
    setToken('');
    setWsTokenValue('');
    window.location.reload();
  };

  return (
    <section className="rounded border border-gray-800 bg-gray-900 p-4 space-y-3">
      <div>
        <h2 className="font-semibold">API 访问令牌</h2>
        <p className="mt-1 text-sm text-gray-400">仅保存在当前浏览器会话中，不会写入前端代码或仓库。</p>
      </div>
      <input
        type="password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        placeholder="输入 API_TOKEN"
        autoComplete="off"
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white"
      />
      <input
        type="password"
        value={wsToken}
        onChange={(event) => setWsTokenValue(event.target.value)}
        placeholder="输入 WS_TOKEN（未设置时可留空）"
        autoComplete="off"
        className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-white"
      />
      <div className="flex gap-2">
        <button onClick={save} disabled={!token.trim()} className="rounded bg-blue-600 px-3 py-2 disabled:opacity-50">保存并重连</button>
        <button onClick={clear} className="rounded bg-gray-700 px-3 py-2">清除</button>
      </div>
    </section>
  );
}
