'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { RiskConfigCard } from '@/components/risk/RiskConfigCard';
import { KillSwitchToggle } from '@/components/risk/KillSwitchToggle';
import { ConfigVersionManager } from '@/components/risk/ConfigVersionManager';

export default function RiskPage() {
  const { data: status, isError: statusError } = useQuery({
    queryKey: ['systemStatus'],
    queryFn: () => api.getSystemStatus(),
    refetchInterval: 5000,
  });
  const { data: activeConfigs, isError: configError, error } = useQuery({
    queryKey: ['activeConfigs'],
    queryFn: () => api.getActiveConfigs(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">风控中心</h1>
      {statusError && <p className="text-red-400 text-sm">系统状态加载失败</p>}
      {configError && (
        <p className="text-red-400 text-sm">配置加载失败：{(error as Error).message}</p>
      )}
      <KillSwitchToggle enabled={status?.kill_switch ?? true} executionEnabled={status?.execution_enabled ?? false} />
      <RiskConfigCard configs={activeConfigs?.risk} />
      <ConfigVersionManager />
    </div>
  );
}