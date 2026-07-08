'use client';
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

const MIN_EQUITY = 1; // 最小权益 1 USDT
const MAX_EQUITY = 10_000_000; // 最大权益 1000 万 USDT

export function EquityEditor() {
  const qc = useQueryClient();
  const { data: settings, isLoading } = useQuery({
    queryKey: ['user-settings'],
    queryFn: () => api.getUserSettings(),
  });
  const [equity, setEquity] = useState<string>('');
  const [mode, setMode] = useState<string>('training');
  const [validationError, setValidationError] = useState<string | null>(null);

  // settings 变更时同步到本地 state（移除 initialized 锁，允许外部变更同步）
  useEffect(() => {
    if (settings) {
      setEquity(settings.account_equity ?? '1500');
      setMode(settings.mode ?? 'training');
      setValidationError(null);
    }
  }, [settings]);

  const updateMut = useMutation({
    mutationFn: () => api.updateUserSettings({ account_equity: equity, mode }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['user-settings'] });
    },
  });

  const handleSave = () => {
    setValidationError(null);
    const num = parseFloat(equity);
    if (!equity || isNaN(num)) {
      setValidationError('请输入有效数字');
      return;
    }
    if (num < MIN_EQUITY) {
      setValidationError(`权益不能小于 ${MIN_EQUITY} USDT`);
      return;
    }
    if (num > MAX_EQUITY) {
      setValidationError(`权益不能超过 ${MAX_EQUITY} USDT`);
      return;
    }
    updateMut.mutate();
  };

  if (isLoading) return <p className="text-gray-500 text-sm">加载中...</p>;

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">账户权益</h3>
      <div className="flex gap-2 items-end">
        <label className="flex-1">
          <span className="text-xs text-gray-500">USDT</span>
          <input value={equity} onChange={(e) => setEquity(e.target.value)} type="number"
            min={MIN_EQUITY} step="0.01"
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
          onClick={handleSave}
          disabled={updateMut.isPending}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded text-sm"
        >
          {updateMut.isPending ? '保存中...' : '保存'}
        </button>
      </div>
      {validationError && (
        <p className="text-xs text-red-400 mt-2">{validationError}</p>
      )}
      {updateMut.isError && (
        <p className="text-xs text-red-400 mt-2">保存失败：{(updateMut.error as Error).message}</p>
      )}
      {updateMut.isSuccess && !validationError && (
        <p className="text-xs text-green-400 mt-2">已保存</p>
      )}
    </div>
  );
}
