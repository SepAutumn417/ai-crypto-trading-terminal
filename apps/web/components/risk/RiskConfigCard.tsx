'use client';
import type { ConfigVersion } from '@/lib/api';

export function RiskConfigCard({ configs }: { configs?: ConfigVersion | null }) {
  if (!configs) return null;
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">风险配置 ({configs.version_label})</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        {Object.entries(configs.payload).map(([k, v]) => (
          <div key={k}><span className="text-gray-500">{k}:</span> <span className="font-mono">{String(v)}</span></div>
        ))}
      </div>
    </div>
  );
}