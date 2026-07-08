'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function KillSwitchToggle({ enabled, executionEnabled }: { enabled: boolean; executionEnabled: boolean }) {
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const toggleKill = useMutation({
    mutationFn: (v: boolean) => api.toggleKillSwitch(v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['systemStatus'] });
      setConfirming(false);
    },
  });
  const toggleExec = useMutation({
    mutationFn: (v: boolean) => api.toggleExecutionMode(v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['systemStatus'] }),
  });

  const handleKillClick = () => {
    // 开启 Kill Switch 是危险操作（停摆整个交易系统），需要二次确认
    // 关闭 Kill Switch 无需确认
    if (!enabled) {
      setConfirming(true);
    } else {
      toggleKill.mutate(false);
    }
  };

  const handleConfirm = () => {
    toggleKill.mutate(true);
  };

  return (
    <div className="p-4 border border-gray-800 rounded space-y-3">
      <h3 className="font-bold">系统开关</h3>
      <div className="flex items-center gap-3">
        <span className="text-sm">Kill Switch</span>
        <span className={`inline-block w-3 h-3 rounded-full ${enabled ? 'bg-red-500' : 'bg-green-500'}`} />
        {!confirming ? (
          <button
            onClick={handleKillClick}
            disabled={toggleKill.isPending}
            className={`text-xs px-3 py-1 border rounded hover:bg-gray-800 disabled:opacity-50 ${
              !enabled ? 'border-red-600 text-red-400' : 'border-gray-700'
            }`}
          >
            {toggleKill.isPending ? '处理中...' : enabled ? '关闭' : '开启'}
          </button>
        ) : (
          <span className="flex items-center gap-2">
            <span className="text-xs text-red-400">确认开启？将停摆所有交易</span>
            <button
              onClick={handleConfirm}
              disabled={toggleKill.isPending}
              className="text-xs px-2 py-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded"
            >
              {toggleKill.isPending ? '处理中...' : '确认开启'}
            </button>
            <button
              onClick={() => setConfirming(false)}
              disabled={toggleKill.isPending}
              className="text-xs px-2 py-1 border border-gray-700 rounded hover:bg-gray-800"
            >
              取消
            </button>
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm">Execution Mode</span>
        <button
          onClick={() => toggleExec.mutate(!executionEnabled)}
          disabled={toggleExec.isPending}
          className={`text-xs px-3 py-1 rounded disabled:opacity-50 ${executionEnabled ? 'bg-green-600' : 'bg-gray-700'}`}
        >
          {toggleExec.isPending ? '处理中...' : executionEnabled ? 'ON' : 'OFF'}
        </button>
      </div>
      {toggleKill.isError && (
        <p className="text-xs text-red-400">操作失败：{(toggleKill.error as Error).message}</p>
      )}
    </div>
  );
}
