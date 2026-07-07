'use client';
const statusColors: Record<string, string> = {
  ALLOW: 'bg-green-600', ALLOW_CONFIRM: 'bg-green-600',
  WARN: 'bg-yellow-600', REDUCE_RISK: 'bg-orange-600', BLOCK: 'bg-red-600',
};

export function RiskCard({ risk }: { risk: any }) {
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h4 className="font-bold mb-2">风控检查</h4>
      <div className="flex items-center gap-3 mb-2">
        <span className={`px-2 py-1 rounded text-sm ${statusColors[risk.status] || 'bg-gray-600'}`}>{risk.status}</span>
        <span className="text-xs text-gray-500">max risk %: {risk.max_allowed_risk_percent}</span>
      </div>
      {risk.block_reasons?.length > 0 && (
        <ul className="text-red-400 text-xs list-disc pl-4 mt-2">
          {risk.block_reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}
        </ul>
      )}
      {risk.warnings?.length > 0 && (
        <ul className="text-yellow-400 text-xs list-disc pl-4 mt-2">
          {risk.warnings.map((r: string, i: number) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}