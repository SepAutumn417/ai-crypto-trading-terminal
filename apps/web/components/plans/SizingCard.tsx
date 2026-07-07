'use client';
export function SizingCard({ sizing }: { sizing: any }) {
  return (
    <div className="p-4 border border-gray-800 rounded">
      <h4 className="font-bold mb-2">仓位计算</h4>
      <div className="grid grid-cols-3 gap-2 text-sm">
        <Field label="风险金额" v={sizing.risk_amount} />
        <Field label="名义仓位" v={sizing.notional_value} />
        <Field label="圆整后数量" v={sizing.rounded_size} />
        <Field label="所需保证金" v={sizing.required_margin} />
        <Field label="预估手续费" v={sizing.estimated_fee} />
        <Field label="盈亏比" v={sizing.risk_reward_ratio} />
        <Field label="止损预估亏损" v={sizing.estimated_loss_at_stop} />
      </div>
      {sizing.sizing_warnings?.length > 0 && (
        <div className="mt-2 text-yellow-400 text-xs">
          警告: {sizing.sizing_warnings.join('; ')}
        </div>
      )}
    </div>
  );
}

function Field({ label, v }: { label: string; v: any }) {
  return <div><span className="text-gray-500">{label}:</span> <span className="font-mono">{v}</span></div>;
}