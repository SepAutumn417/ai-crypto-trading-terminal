'use client';
import { ComprehensiveAIEvaluation } from '@/lib/api';

const actionConfig: Record<
  string,
  { label: string; className: string }
> = {
  WAIT: { label: '等待', className: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40' },
  ALLOW_CONFIRM: { label: '允许确认', className: 'bg-green-500/20 text-green-300 border-green-500/40' },
  REDUCE_RISK: { label: '降低风险', className: 'bg-orange-500/20 text-orange-300 border-orange-500/40' },
  DO_NOT_TRADE: { label: '禁止交易', className: 'bg-red-500/20 text-red-300 border-red-500/40' },
};

const sourceConfig: Record<
  string,
  { label: string; className: string }
> = {
  llm: { label: 'LLM', className: 'bg-blue-500/20 text-blue-300 border-blue-500/40' },
  rule_based: { label: '规则引擎', className: 'bg-gray-500/20 text-gray-300 border-gray-500/40' },
};

function ExplanationRow({ label, content }: { label: string; content: string }) {
  return (
    <div className="flex gap-2 text-sm">
      <span className="text-gray-400 whitespace-nowrap min-w-[72px]">{label}</span>
      <span className="text-gray-200 leading-relaxed">{content}</span>
    </div>
  );
}

function ListSection({
  title,
  items,
  accent,
}: {
  title: string;
  items: string[];
  accent: string;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div className="bg-gray-800/40 rounded-lg p-3">
      <div className={`text-xs font-semibold mb-1.5 ${accent}`}>{title}</div>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-gray-300 flex gap-1.5">
            <span className="text-gray-600 select-none">·</span>
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AIExplanationPanel({ evaluation }: { evaluation: ComprehensiveAIEvaluation }) {
  const explanation = evaluation.explanation;

  if (!explanation) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 border border-blue-800 text-center text-gray-500 text-sm">
        暂无 AI 结构化解释数据
      </div>
    );
  }

  const action = actionConfig[explanation.recommendedAction] || actionConfig.WAIT;
  const source = sourceConfig[evaluation.source] || sourceConfig.rule_based;

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-blue-800 space-y-3">
      {/* 头部：来源标签 + 建议操作 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-blue-300">AI 评估解释</span>
          <span className={`text-xs px-2 py-0.5 rounded border ${source.className}`}>
            {source.label}
          </span>
        </div>
        <span className={`text-xs px-2 py-1 rounded border font-medium ${action.className}`}>
          建议操作：{action.label}
        </span>
      </div>

      {/* 摘要 */}
      <div className="p-3 bg-gray-800/50 rounded-lg">
        <div className="text-xs text-gray-400 mb-1">评估摘要</div>
        <div className="text-sm text-gray-200 leading-relaxed">{explanation.summary}</div>
      </div>

      {/* 结构化解释 */}
      <div className="space-y-2 px-1">
        <ExplanationRow label="市场状态" content={explanation.marketStateExplanation} />
        <ExplanationRow label="计划质量" content={explanation.planQualityExplanation} />
        <ExplanationRow label="风险评估" content={explanation.riskExplanation} />
        <ExplanationRow label="机会评级" content={explanation.opportunityGradeComment} />
      </div>

      {/* 列表区 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <ListSection title="警告" items={explanation.warnings} accent="text-yellow-400" />
        <ListSection title="升级条件" items={explanation.upgradeConditions} accent="text-green-400" />
        <ListSection title="失效条件" items={explanation.invalidationConditions} accent="text-red-400" />
        <ListSection title="情绪风险" items={explanation.emotionalRiskFlags} accent="text-purple-400" />
      </div>

      {/* 安全提示 */}
      <div className="p-2.5 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
        <p className="text-xs text-yellow-300/80 leading-relaxed">
          该评估基于当前数据和规则，不构成盈利保证。真实交易必须以风控引擎和用户确认结果为准。
        </p>
      </div>
    </div>
  );
}
