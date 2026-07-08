'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useWebSocketInvalidation } from '@/lib/useWebSocket';

export function SystemStatusBadge() {
  const qc = useQueryClient();
  const { data: status } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: () => api.getSystemStatus(),
    // WebSocket 接收到 system 频道推送时会 invalidate，无需轮询
    refetchInterval: false,
  });
  // 订阅 system 频道，收到状态变更时刷新
  useWebSocketInvalidation('system', ['systemStatus']);
  const toggleKill = useMutation({
    mutationFn: (enabled: boolean) => api.toggleKillSwitch(enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['systemStatus'] }),
  });
  const toggleExec = useMutation({
    mutationFn: (enabled: boolean) => api.toggleExecutionMode(enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['systemStatus'] }),
  });

  if (!status) return null;

  return (
    <div className="flex items-center gap-3">
      <span className={`inline-block w-3 h-3 rounded-full ${status.kill_switch ? 'bg-red-500' : 'bg-green-500'}`}
        title={status.kill_switch ? 'Kill Switch ON' : 'Kill Switch OFF'} />
      <span className="text-sm">Kill Switch</span>
      <button onClick={() => toggleKill.mutate(!status.kill_switch)}
        className="text-xs px-2 py-1 border border-gray-700 rounded hover:bg-gray-800">
        {status.kill_switch ? '关闭' : '开启'}
      </button>
      <span className="text-sm ml-3">Execution</span>
      <button onClick={() => toggleExec.mutate(!status.execution_enabled)}
        className={`text-xs px-2 py-1 rounded ${status.execution_enabled ? 'bg-green-600' : 'bg-gray-700'}`}>
        {status.execution_enabled ? 'ON' : 'OFF'}
      </button>
    </div>
  );
}