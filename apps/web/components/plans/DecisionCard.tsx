'use client';
const colors: Record<string, string> = {
  ALLOW_CONFIRM: 'bg-green-600', REDUCE_RISK: 'bg-orange-600',
  WAIT: 'bg-yellow-600', BLOCK: 'bg-red-600', EXPIRED: 'bg-gray-600',
};

export function DecisionCard({ decision }: { decision: any }) {
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h4 className="font-bold mb-2">决策门</h4>
      <span className={`px-2 py-1 rounded text-sm ${colors[decision.result] || 'bg-gray-600'}`}>{decision.result}</span>
      {decision.reasons?.length > 0 && (
        <ul className="text-xs text-gray-400 list-disc pl-4 mt-2">
          {decision.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}