'use client';
import type { ConfigVersion } from '@/lib/api';
export function OpportunityGradeEditor({ activeConfig }: { activeConfig?: ConfigVersion | null }) {
  if (!activeConfig) return null;
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">机会等级（{activeConfig.version_label}）</h3>
      <pre className="text-xs bg-gray-950 p-2 rounded overflow-x-auto">
        {JSON.stringify(activeConfig.payload, null, 2)}
      </pre>
    </div>
  );
}