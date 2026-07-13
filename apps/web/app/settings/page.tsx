'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { EquityEditor } from '@/components/settings/EquityEditor';
import { RiskConfigEditor } from '@/components/settings/RiskConfigEditor';
import { ExecutionConfigEditor } from '@/components/settings/ExecutionConfigEditor';
import { OpportunityGradeEditor } from '@/components/settings/OpportunityGradeEditor';
import { SymbolRulesEditor } from '@/components/settings/SymbolRulesEditor';
import { ApiAccessSettings } from '@/components/settings/ApiAccessSettings';

export default function SettingsPage() {
  const { data: activeConfigs, isError, error } = useQuery({
    queryKey: ['activeConfigs'],
    queryFn: () => api.getActiveConfigs(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      {isError && (
        <p className="text-red-400 text-sm">加载配置失败：{(error as Error).message}</p>
      )}
      <ApiAccessSettings />
      <EquityEditor />
      <RiskConfigEditor activeConfig={activeConfigs?.risk} />
      <ExecutionConfigEditor activeConfig={activeConfigs?.execution} />
      <OpportunityGradeEditor activeConfig={activeConfigs?.opportunity_grade} />
      <SymbolRulesEditor activeConfig={activeConfigs?.symbol_rules} />
    </div>
  );
}
