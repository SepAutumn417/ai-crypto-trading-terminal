'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type ConfigVersion, type CreateConfigInput } from '@/lib/api';

interface OpportunityGradePayload {
  a_max_risk_percent: number;
  b_max_risk_percent: number;
  c_max_risk_percent: number;
  blocked_max_risk_percent: number;
}

const GRADE_FIELDS: { key: keyof OpportunityGradePayload; label: string }[] = [
  { key: 'a_max_risk_percent', label: 'A 级最大风险比例' },
  { key: 'b_max_risk_percent', label: 'B 级最大风险比例' },
  { key: 'c_max_risk_percent', label: 'C 级最大风险比例' },
  { key: 'blocked_max_risk_percent', label: 'BLOCKED 级最大风险比例' },
];

export function OpportunityGradeEditor({ activeConfig }: { activeConfig?: ConfigVersion | null }) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [versionLabel, setVersionLabel] = useState('');
  const [form, setForm] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (input: CreateConfigInput) => api.createConfig(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['activeConfigs'] });
      qc.invalidateQueries({ queryKey: ['configs', 'opportunity_grade'] });
      setShowForm(false);
      setVersionLabel('');
      setForm({});
      setFormError(null);
    },
  });

  if (!activeConfig) return null;

  const payload = activeConfig.payload as OpportunityGradePayload;

  const openForm = () => {
    const initial: Record<string, string> = {};
    GRADE_FIELDS.forEach((f) => {
      initial[f.key] = String(payload[f.key] ?? '');
    });
    setForm(initial);
    setVersionLabel('');
    setFormError(null);
    setShowForm(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!versionLabel.trim()) {
      setFormError('请输入版本标签');
      return;
    }
    const payloadOut: Record<string, unknown> = {};
    for (const f of GRADE_FIELDS) {
      const raw = form[f.key];
      const num = Number(raw);
      if (raw === '' || isNaN(num)) {
        setFormError(`字段 "${f.label}" 需要有效数值`);
        return;
      }
      payloadOut[f.key] = num;
    }
    createMut.mutate({
      config_type: 'opportunity_grade',
      version_label: versionLabel.trim(),
      payload: payloadOut,
    });
  };

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">机会等级（{activeConfig.version_label}）</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {GRADE_FIELDS.map((f) => (
          <div key={f.key} className="flex justify-between border-b border-gray-800 py-1">
            <dt className="text-gray-400">{f.label}</dt>
            <dd className="font-mono text-right text-gray-100">{String(payload[f.key] ?? '-')}</dd>
          </div>
        ))}
      </dl>

      {!showForm ? (
        <button
          onClick={openForm}
          className="mt-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm"
        >
          新建版本
        </button>
      ) : (
        <div className="mt-4 border-t border-gray-800 pt-4">
          <h4 className="text-sm font-bold mb-2 text-gray-200">新建机会等级配置版本</h4>
          <div className="space-y-2">
            <label className="block">
              <span className="text-xs text-gray-500">版本标签（必填）</span>
              <input
                value={versionLabel}
                onChange={(e) => setVersionLabel(e.target.value)}
                placeholder="如 v2"
                className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              {GRADE_FIELDS.map((f) => (
                <label key={f.key} className="block">
                  <span className="text-xs text-gray-500">{f.label} (%)</span>
                  <input
                    type="number"
                    step="any"
                    value={form[f.key] ?? ''}
                    onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"
                  />
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={handleSubmit}
              disabled={createMut.isPending}
              className="px-3 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white rounded text-sm"
            >
              {createMut.isPending ? '提交中...' : '提交新版本'}
            </button>
            <button
              onClick={() => {
                setShowForm(false);
                setFormError(null);
              }}
              className="px-3 py-1 border border-gray-700 text-gray-300 rounded text-sm hover:bg-gray-800"
            >
              取消
            </button>
          </div>
          {formError && <p className="text-xs text-red-400 mt-2">{formError}</p>}
          {createMut.isError && (
            <p className="text-xs text-red-400 mt-2">
              提交失败：{(createMut.error as Error)?.message || '未知错误'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
