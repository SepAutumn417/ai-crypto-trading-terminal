'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { EquityEditor } from '@/components/settings/EquityEditor';
import { RiskConfigEditor } from '@/components/settings/RiskConfigEditor';
import { ExecutionConfigEditor } from '@/components/settings/ExecutionConfigEditor';
import { OpportunityGradeEditor } from '@/components/settings/OpportunityGradeEditor';
import { SymbolRulesEditor } from '@/components/settings/SymbolRulesEditor';

export default function SettingsPage() {
  const { data: settings } = useQuery({
    queryKey: ['userSettings'],
    queryFn: () => api.getUserSettings(),
  });
  const { data: activeConfigs } = useQuery({
    queryKey: ['activeConfigs'],
    queryFn: () => api.getActiveConfigs(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      <EquityEditor initialEquity={settings?.account_equity} />
      <RiskConfigEditor activeConfig={activeConfigs?.risk} />
      <ExecutionConfigEditor activeConfig={activeConfigs?.execution} />
      <OpportunityGradeEditor activeConfig={activeConfigs?.opportunity_grade} />
      <SymbolRulesEditor activeConfig={activeConfigs?.symbol_rules} />
    </div>
  );
}