'use client';
import type { ConfigVersion } from '@/lib/api';
export function RiskConfigEditor({ activeConfig }: { activeConfig?: ConfigVersion | null }) {
  if (!activeConfig) return null;
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">风控配置（{activeConfig.version_label}）</h3>
      <pre className="text-xs bg-gray-950 p-2 rounded overflow-x-auto">
        {JSON.stringify(activeConfig.payload, null, 2)}
      </pre>
      <p className="text-xs text-gray-500 mt-2">在 Risk Center 页面管理新版本。</p>
    </div>
  );
}