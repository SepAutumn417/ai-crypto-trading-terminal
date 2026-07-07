'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function EquityEditor({ initialEquity }: { initialEquity?: string | null }) {
  const [equity, setEquity] = useState(initialEquity ?? '1500');
  const qc = useQueryClient();
  const saveMut = useMutation({
    mutationFn: () => api.toggleExecutionMode(false),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['userSettings'] }),
  });
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">账户权益</h3>
      <div className="flex gap-2 items-end">
        <label className="flex-1">
          <span className="text-xs text-gray-500">USDT</span>
          <input value={equity} onChange={(e) => setEquity(e.target.value)} type="number"
            className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <button onClick={() => alert('保存')} className="px-3 py-1 bg-blue-600 rounded text-sm">保存</button>
      </div>
      <p className="text-xs text-gray-500 mt-2">v0.1：UI 占位，实际需独立 PUT /api/settings 端点。</p>
    </div>
  );
}