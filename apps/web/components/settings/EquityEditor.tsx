'use client';
import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function EquityEditor() {
  const qc = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ['user-settings'],
    queryFn: () => api.getUserSettings(),
  });
  const [equity, setEquity] = useState<string>('');
  const [mode, setMode] = useState<string>('training');

  // settings 加载后同步到本地 state
  const initialized = useRef(false);
  useEffect(() => {
    if (settings && !initialized.current) {
      setEquity(settings.account_equity ?? '1500');
      setMode(settings.mode ?? 'training');
      initialized.current = true;
    }
  }, [settings]);

  const updateMut = useMutation({
    mutationFn: () => api.updateUserSettings({ account_equity: equity, mode }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['user-settings'] });
    },
  });

  if (isLoading) return <p className="text-gray-500 text-sm">加载中...</p>;

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">账户权益</h3>
      <div className="flex gap-2 items-end">
        <label className="flex-1">
          <span className="text-xs text-gray-500">USDT</span>
          <input value={equity} onChange={(e) => setEquity(e.target.value)} type="number"
            className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label>
          <span className="text-xs text-gray-500">模式</span>
          <select value={mode} onChange={(e) => setMode(e.target.value)}
            className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded">
            <option value="training">training</option>
            <option value="live">live</option>
          </select>
        </label>
        <button
          onClick={() => updateMut.mutate()}
          disabled={updateMut.isPending}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded text-sm"
        >
          {updateMut.isPending ? '保存中...' : '保存'}
        </button>
      </div>
      {updateMut.isError && (
        <p className="text-xs text-red-400 mt-2">保存失败：{(updateMut.error as Error).message}</p>
      )}
      {updateMut.isSuccess && (
        <p className="text-xs text-green-400 mt-2">已保存</p>
      )}
    </div>
  );
}
