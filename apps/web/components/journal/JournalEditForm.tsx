'use client';
import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type TradeJournal } from '@/lib/api';

interface JournalEditFormProps {
  journal: TradeJournal;
  onClose: () => void;
}

export function JournalEditForm({ journal, onClose }: JournalEditFormProps) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    exit_price: journal.exit_price || '',
    exit_reason: journal.exit_reason || '',
    lessons_learned: journal.lessons_learned || '',
    emotions: journal.emotions || '',
    status: journal.status,
    exit_at: journal.exit_at ? journal.exit_at.slice(0, 16) : '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    setForm({
      exit_price: journal.exit_price || '',
      exit_reason: journal.exit_reason || '',
      lessons_learned: journal.lessons_learned || '',
      emotions: journal.emotions || '',
      status: journal.status,
      exit_at: journal.exit_at ? journal.exit_at.slice(0, 16) : '',
    });
    setErrors({});
  }, [journal]);

  const updateMut = useMutation({
    mutationFn: (data: Partial<TradeJournal>) => api.updateJournal(journal.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['journal', journal.id] });
      qc.invalidateQueries({ queryKey: ['journals'] });
      qc.invalidateQueries({ queryKey: ['journalSummary'] });
      onClose();
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => api.deleteJournal(journal.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['journals'] });
      qc.invalidateQueries({ queryKey: ['journalSummary'] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    // exit_price 数值校验
    if (form.exit_price) {
      const num = parseFloat(form.exit_price);
      if (isNaN(num) || num <= 0) {
        newErrors.exit_price = '出场价格必须是正数';
      }
    }

    // CLOSED 状态必填校验
    if (form.status === 'CLOSED') {
      if (!form.exit_price) {
        newErrors.exit_price = '已平仓状态必须填写出场价格';
      }
      if (!form.exit_at) {
        newErrors.exit_at = '已平仓状态必须填写出场时间';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    setErrors({});

    const payload: Record<string, unknown> = {};
    if (form.exit_price) payload.exit_price = form.exit_price;
    if (form.exit_reason) payload.exit_reason = form.exit_reason;
    if (form.lessons_learned) payload.lessons_learned = form.lessons_learned;
    if (form.emotions) payload.emotions = form.emotions;
    payload.status = form.status;
    if (form.exit_at) payload.exit_at = new Date(form.exit_at).toISOString();
    updateMut.mutate(payload);
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 space-y-4 border border-blue-800">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold">编辑交易日志</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="text-sm">出场价格
            <input
              type="text"
              value={form.exit_price}
              onChange={(e) => setForm({ ...form, exit_price: e.target.value })}
              placeholder="留空表示未平仓"
              className={`block w-full bg-gray-800 border px-2 py-1 rounded mt-1 ${errors.exit_price ? 'border-red-500' : 'border-gray-700'}`}
            />
            {errors.exit_price && <span className="text-xs text-red-400 mt-1 block">{errors.exit_price}</span>}
          </label>
          <label className="text-sm">出场时间
            <input
              type="datetime-local"
              value={form.exit_at}
              onChange={(e) => setForm({ ...form, exit_at: e.target.value })}
              className={`block w-full bg-gray-800 border px-2 py-1 rounded mt-1 ${errors.exit_at ? 'border-red-500' : 'border-gray-700'}`}
            />
            {errors.exit_at && <span className="text-xs text-red-400 mt-1 block">{errors.exit_at}</span>}
          </label>
        </div>

        <label className="text-sm block">状态
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value as 'OPEN' | 'CLOSED' })}
            className="block w-full bg-gray-800 border border-gray-700 px-2 py-1 rounded mt-1"
          >
            <option value="OPEN">进行中</option>
            <option value="CLOSED">已平仓</option>
          </select>
        </label>

        <label className="text-sm block">出场理由
          <textarea
            value={form.exit_reason}
            onChange={(e) => setForm({ ...form, exit_reason: e.target.value })}
            rows={2}
            className="block w-full bg-gray-800 border border-gray-700 px-2 py-1 rounded mt-1 resize-none"
          />
        </label>

        <label className="text-sm block">经验教训
          <textarea
            value={form.lessons_learned}
            onChange={(e) => setForm({ ...form, lessons_learned: e.target.value })}
            rows={3}
            className="block w-full bg-gray-800 border border-gray-700 px-2 py-1 rounded mt-1 resize-none"
          />
        </label>

        <label className="text-sm block">情绪状态
          <input
            type="text"
            value={form.emotions}
            onChange={(e) => setForm({ ...form, emotions: e.target.value })}
            placeholder="如：冷静 / 贪婪 / 恐惧"
            className="block w-full bg-gray-800 border border-gray-700 px-2 py-1 rounded mt-1"
          />
        </label>

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={updateMut.isPending}
            className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 px-4 py-2 rounded font-medium"
          >
            {updateMut.isPending ? '保存中...' : '保存'}
          </button>
          <button
            type="button"
            onClick={() => { if (confirm('确定删除这条交易日志？')) deleteMut.mutate(); }}
            disabled={deleteMut.isPending}
            className="px-4 py-2 bg-red-900 hover:bg-red-800 disabled:bg-gray-700 text-red-300 rounded font-medium"
          >
            删除
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded font-medium"
          >
            取消
          </button>
        </div>

        {updateMut.isError && (
          <p className="text-red-400 text-sm">保存失败：{(updateMut.error as Error).message}</p>
        )}
        {deleteMut.isError && (
          <p className="text-red-400 text-sm">删除失败：{(deleteMut.error as Error).message}</p>
        )}
      </form>
    </div>
  );
}
