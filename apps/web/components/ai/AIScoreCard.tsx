'use client';
import { AIEvaluationResult } from '@/lib/api';

interface AIScoreCardProps {
  data: AIEvaluationResult | null;
  loading?: boolean;
}

const gradeColors: Record<string, string> = {
  A: 'from-green-500 to-emerald-600',
  B: 'from-lime-500 to-green-600',
  C: 'from-yellow-500 to-amber-600',
  D: 'from-orange-500 to-red-600',
  F: 'from-red-500 to-rose-600',
};

const gradeBg: Record<string, string> = {
  A: 'bg-green-500/10 border-green-500/30',
  B: 'bg-lime-500/10 border-lime-500/30',
  C: 'bg-yellow-500/10 border-yellow-500/30',
  D: 'bg-orange-500/10 border-orange-500/30',
  F: 'bg-red-500/10 border-red-500/30',
};

export function AIScoreCard({ data, loading }: AIScoreCardProps) {
  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 animate-pulse">
        <div className="h-8 bg-gray-800 rounded w-1/3 mb-4" />
        <div className="h-24 bg-gray-800 rounded mb-4" />
        <div className="h-4 bg-gray-800 rounded w-2/3" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 text-center text-gray-500">
        输入参数以获取指标评分
      </div>
    );
  }

  const score = parseFloat(data.overall_score);
  const gradeColor = gradeColors[data.grade] || gradeColors.C;
  const gradeBgClass = gradeBg[data.grade] || gradeBg.C;

  return (
    <div className={`rounded-lg p-6 border ${gradeBgClass}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-gray-400 text-sm">指标综合评分</div>
          <div className="text-4xl font-bold mt-1">
            {data.grade}
            <span className="text-lg text-gray-400 ml-2">{data.recommendation}</span>
          </div>
        </div>
        <div className={`text-5xl font-bold bg-gradient-to-r ${gradeColor} bg-clip-text text-transparent`}>
          {score.toFixed(1)}
        </div>
      </div>

      <div className="w-full bg-gray-800 rounded-full h-3 mb-4">
        <div
          className={`h-3 rounded-full bg-gradient-to-r ${gradeColor}`}
          style={{ width: `${score}%` }}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-gray-400">风险等级：</span>
          <span>{data.risk_level}</span>
        </div>
        <div>
          <span className="text-gray-400">置信度：</span>
          <span>{parseFloat(data.conviction).toFixed(1)}%</span>
        </div>
      </div>

      <div className="mt-4 p-3 bg-gray-800/50 rounded-lg text-sm">
        <div className="text-gray-400 mb-1">评估摘要</div>
        <div className="text-gray-200">{data.summary}</div>
      </div>
    </div>
  );
}
