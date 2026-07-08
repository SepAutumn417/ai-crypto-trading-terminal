'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { JournalSummary } from '@/components/journal/JournalSummary';
import { JournalList } from '@/components/journal/JournalList';
import { JournalDetail } from '@/components/journal/JournalDetail';
import { JournalEditForm } from '@/components/journal/JournalEditForm';
import { useWebSocketInvalidation } from '@/lib/useWebSocket';

export default function JournalPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [filter, setFilter] = useState<{ status?: string; symbol?: string }>({});

  const { data: summary, isError: summaryError } = useQuery({
    queryKey: ['journalSummary', filter.symbol],
    queryFn: () => api.getJournalSummary(filter.symbol),
  });

  const { data: listData, isLoading, isError: listError, error } = useQuery({
    queryKey: ['journals', filter],
    queryFn: () => api.getJournals({ ...filter, page_size: 50 }),
  });

  const { data: selectedJournal } = useQuery({
    queryKey: ['journal', selectedId],
    queryFn: () => selectedId ? api.getJournal(selectedId) : null,
    enabled: !!selectedId,
  });

  // 订阅 journals 频道：日志变更时实时刷新
  useWebSocketInvalidation('journals', ['journals', 'journal', 'journalSummary']);

  const items = listData?.items || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">交易日志</h1>
        <div className="flex gap-2">
          <select
            value={filter.status || ''}
            onChange={(e) => setFilter({ ...filter, status: e.target.value || undefined })}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
          >
            <option value="">全部状态</option>
            <option value="OPEN">进行中</option>
            <option value="CLOSED">已平仓</option>
          </select>
          <select
            value={filter.symbol || ''}
            onChange={(e) => setFilter({ ...filter, symbol: e.target.value || undefined })}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm"
          >
            <option value="">全部交易对</option>
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
            <option value="SOLUSDT">SOLUSDT</option>
          </select>
        </div>
      </div>

      {summaryError && (
        <p className="text-red-400 text-sm">加载统计失败</p>
      )}
      <JournalSummary data={summary || null} />

      {listError && (
        <p className="text-red-400 text-sm">加载日志失败：{(error as Error).message}</p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-xl font-bold">交易记录</h2>
          <JournalList
            items={items}
            onSelect={setSelectedId}
            selectedId={selectedId}
          />
        </div>
        <div className="lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold">交易详情</h2>
            {selectedJournal && !editing && (
              <button
                onClick={() => setEditing(true)}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium"
              >
                编辑 / 平仓
              </button>
            )}
          </div>
          {selectedJournal && editing ? (
            <JournalEditForm
              journal={selectedJournal}
              onClose={() => setEditing(false)}
            />
          ) : (
            <JournalDetail journal={selectedJournal || null} />
          )}
        </div>
      </div>
    </div>
  );
}
