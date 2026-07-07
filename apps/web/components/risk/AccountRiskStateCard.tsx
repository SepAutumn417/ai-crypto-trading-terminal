'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function AccountRiskStateCard() {
  const { data } = useQuery({
    queryKey: ['accountRiskState'],
    queryFn: async () => {
      const configs = await api.getActiveConfigs();
      return configs.risk?.payload ?? null;
    },
  });
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">账户风险状态</h3>
      <p className="text-xs text-gray-500">v0.1：账户状态由系统维护，UI 显示当前值。</p>
      <div className="text-sm text-gray-400 mt-2">
        当日亏损 R、连续亏损次数、冷却期 — 需从独立 API 端点读取（v0.1 默认初始值 0/0/null）。
      </div>
    </div>
  );
}