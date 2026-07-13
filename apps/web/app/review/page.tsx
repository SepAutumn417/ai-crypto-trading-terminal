'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type TradeJournal } from '@/lib/api';
import { JournalSummary } from '@/components/journal/JournalSummary';

type ReviewResult = {
  summary: string;
  emotionalAnalysis?: string;
  lessonSummary?: string;
  improvementSuggestions?: string[];
  source: string;
};

export default function ReviewPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const summary = useQuery({ queryKey: ['review-summary'], queryFn: () => api.getJournalSummary() });
  const journals = useQuery({
    queryKey: ['review-journals'],
    queryFn: () => api.getJournals({ status: 'CLOSED', page: 1, page_size: 50 }),
  });
  const review = useMutation({ mutationFn: (journalId: string) => api.reviewTrade(journalId) as Promise<ReviewResult> });
  const selected = journals.data?.items.find((journal) => journal.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">交易复盘</h2>
        <p className="text-sm text-gray-400">基于已平仓交易统计表现，并按需生成单笔交易的 AI 复盘。</p>
      </div>
      <JournalSummary data={summary.data ?? null} />
      {summary.isError && <p className="text-sm text-red-300">统计加载失败：{(summary.error as Error).message}</p>}
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded border border-gray-800 bg-gray-900 p-4 lg:col-span-1">
          <h3 className="mb-3 font-semibold">已平仓交易</h3>
          {journals.isError && <p className="text-sm text-red-300">日志加载失败。</p>}
          {!journals.isLoading && !journals.data?.items.length && <p className="text-sm text-gray-500">暂无可复盘的已平仓交易。</p>}
          <div className="space-y-2">{journals.data?.items.map((journal) => (
            <JournalRow key={journal.id} journal={journal} selected={journal.id === selectedId} onSelect={() => setSelectedId(journal.id)} />
          ))}</div>
        </section>
        <section className="rounded border border-gray-800 bg-gray-900 p-4 lg:col-span-2">
          <h3 className="mb-3 font-semibold">AI 复盘</h3>
          {!selected && <p className="text-sm text-gray-500">从左侧选择一笔已平仓交易开始复盘。</p>}
          {selected && <>
            <div className="mb-4 grid grid-cols-2 gap-3 text-sm"><span>标的：{selected.symbol}</span><span>方向：{selected.direction}</span><span>盈亏：{selected.pnl ?? '-'}</span><span>情绪：{selected.emotions ?? '-'}</span></div>
            <button onClick={() => review.mutate(selected.id)} disabled={review.isPending} className="rounded bg-purple-600 px-4 py-2 disabled:bg-gray-700">
              {review.isPending ? '生成中...' : '生成 AI 复盘'}
            </button>
          </>}
          {review.isError && <p className="mt-3 text-sm text-red-300">复盘生成失败：{(review.error as Error).message}</p>}
          {review.data && <div className="mt-4 space-y-4 rounded bg-gray-800 p-4 text-sm"><p className="text-xs text-gray-500">来源：{review.data.source}</p><Block title="总结" value={review.data.summary} /><Block title="情绪分析" value={review.data.emotionalAnalysis} /><Block title="经验教训" value={review.data.lessonSummary} />{review.data.improvementSuggestions?.length ? <div><h4 className="mb-1 font-medium">改进建议</h4><ul className="list-disc space-y-1 pl-5">{review.data.improvementSuggestions.map((suggestion) => <li key={suggestion}>{suggestion}</li>)}</ul></div> : null}</div>}
        </section>
      </div>
    </div>
  );
}

function JournalRow({ journal, selected, onSelect }: { journal: TradeJournal; selected: boolean; onSelect: () => void }) {
  return <button onClick={onSelect} className={`w-full rounded border p-3 text-left text-sm ${selected ? 'border-purple-500 bg-purple-950/30' : 'border-gray-800 hover:bg-gray-800'}`}><div className="flex justify-between"><span className="font-medium">{journal.symbol}</span><span className={Number(journal.pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}>{journal.pnl ?? '-'}</span></div><p className="mt-1 text-xs text-gray-400">{journal.direction} · {new Date(journal.exit_at ?? journal.updated_at).toLocaleDateString('zh-CN')}</p></button>;
}

function Block({ title, value }: { title: string; value?: string }) {
  return value ? <div><h4 className="mb-1 font-medium">{title}</h4><p className="whitespace-pre-wrap text-gray-300">{value}</p></div> : null;
}
