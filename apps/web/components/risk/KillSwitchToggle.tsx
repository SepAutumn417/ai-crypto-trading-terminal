'use client';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function KillSwitchToggle({ enabled, executionEnabled }: { enabled: boolean; executionEnabled: boolean }) {
  const qc = useQueryClient();
  const toggleKill = useMutation({
    mutationFn: (v: boolean) => api.toggleKillSwitch(v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['systemStatus'] }),
  });
  const toggleExec = useMutation({
    mutationFn: (v: boolean) => api.toggleExecutionMode(v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['systemStatus'] }),
  });

  return (
    <div className="p-4 border border-gray-800 rounded space-y-3">
      <h3 className="font-bold">系统开关</h3>
      <div className="flex items-center gap-3">
        <span className="text-sm">Kill Switch</span>
        <span className={`inline-block w-3 h-3 rounded-full ${enabled ? 'bg-red-500' : 'bg-green-500'}`} />
        <button onClick={() => toggleKill.mutate(!enabled)}
          className="text-xs px-3 py-1 border border-gray-700 rounded hover:bg-gray-800">
          {enabled ? '关闭' : '开启'}
        </button>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm">Execution Mode</span>
        <button onClick={() => toggleExec.mutate(!executionEnabled)}
          className={`text-xs px-3 py-1 rounded ${executionEnabled ? 'bg-green-600' : 'bg-gray-700'}`}>
          {executionEnabled ? 'ON' : 'OFF'}
        </button>
      </div>
    </div>
  );
}