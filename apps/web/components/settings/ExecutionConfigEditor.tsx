'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type ConfigVersion, type CreateConfigInput } from '@/lib/api';

interface ExecutionPayload {
  enabled: boolean;
  mode: string;
  margin_mode: string;
  allowed_order_types: string[];
  require_stop_loss: boolean;
  require_user_confirmation: boolean;
  require_second_confirmation: boolean;
}

const BOOL_FIELDS: { key: keyof ExecutionPayload; label: string }[] = [
  { key: 'enabled', label: '启用执行' },
  { key: 'require_stop_loss', label: '强制止损' },
  { key: 'require_user_confirmation', label: '需用户确认' },
  { key: 'require_second_confirmation', label: '需二次确认' },
];

const MODE_OPTIONS = ['manual', 'semi_auto', 'full_auto'];
const MARGIN_MODE_OPTIONS = ['isolated', 'crossed'];

function BoolBadge({ value }: { value: boolean }) {
  return value ? (
    <span className="px-2 py-0.5 text-xs rounded bg-green-900 text-green-300">是</span>
  ) : (
    <span className="px-2 py-0.5 text-xs rounded bg-gray-800 text-gray-400">否</span>
  );
}

export function ExecutionConfigEditor({ activeConfig }: { activeConfig?: ConfigVersion | null }) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [versionLabel, setVersionLabel] = useState('');
  const [mode, setMode] = useState('manual');
  const [marginMode, setMarginMode] = useState('isolated');
  const [orderTypes, setOrderTypes] = useState('limit,market');
  const [bools, setBools] = useState<Record<string, boolean>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (input: CreateConfigInput) => api.createConfig(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['activeConfigs'] });
      qc.invalidateQueries({ queryKey: ['configs', 'execution'] });
      setShowForm(false);
      setVersionLabel('');
      setFormError(null);
    },
  });

  if (!activeConfig) return null;

  const payload = activeConfig.payload as ExecutionPayload;

  const openForm = () => {
    setVersionLabel('');
    setMode(payload.mode ?? 'manual');
    setMarginMode(payload.margin_mode ?? 'isolated');
    setOrderTypes((payload.allowed_order_types ?? []).join(','));
    const b: Record<string, boolean> = {};
    BOOL_FIELDS.forEach((f) => {
      b[f.key] = Boolean(payload[f.key]);
    });
    setBools(b);
    setFormError(null);
    setShowForm(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!versionLabel.trim()) {
      setFormError('请输入版本标签');
      return;
    }
    const types = orderTypes
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const payloadOut: Record<string, unknown> = {
      enabled: bools.enabled ?? false,
      mode,
      margin_mode: marginMode,
      allowed_order_types: types,
      require_stop_loss: bools.require_stop_loss ?? false,
      require_user_confirmation: bools.require_user_confirmation ?? false,
      require_second_confirmation: bools.require_second_confirmation ?? false,
    };
    createMut.mutate({
      config_type: 'execution',
      version_label: versionLabel.trim(),
      payload: payloadOut,
    });
  };

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">执行配置（{activeConfig.version_label}）</h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <div className="flex justify-between border-b border-gray-800 py-1">
          <dt className="text-gray-400">执行模式</dt>
          <dd className="font-mono text-right text-gray-100">{String(payload.mode ?? '-')}</dd>
        </div>
        <div className="flex justify-between border-b border-gray-800 py-1">
          <dt className="text-gray-400">保证金模式</dt>
          <dd className="font-mono text-right text-gray-100">{String(payload.margin_mode ?? '-')}</dd>
        </div>
        <div className="flex justify-between border-b border-gray-800 py-1 col-span-2">
          <dt className="text-gray-400">允许订单类型</dt>
          <dd className="font-mono text-right text-gray-100">
            {(payload.allowed_order_types ?? []).join(', ') || '-'}
          </dd>
        </div>
        {BOOL_FIELDS.map((f) => (
          <div key={f.key} className="flex justify-between items-center border-b border-gray-800 py-1">
            <dt className="text-gray-400">{f.label}</dt>
            <dd>
              <BoolBadge value={Boolean(payload[f.key])} />
            </dd>
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
          <h4 className="text-sm font-bold mb-2 text-gray-200">新建执行配置版本</h4>
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
              <label className="block">
                <span className="text-xs text-gray-500">执行模式</span>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                  className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"
                >
                  {MODE_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-gray-500">保证金模式</span>
                <select
                  value={marginMode}
                  onChange={(e) => setMarginMode(e.target.value)}
                  className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"
                >
                  {MARGIN_MODE_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="text-xs text-gray-500">允许订单类型（逗号分隔）</span>
              <input
                value={orderTypes}
                onChange={(e) => setOrderTypes(e.target.value)}
                placeholder="limit,market"
                className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              {BOOL_FIELDS.map((f) => (
                <label key={f.key} className="flex items-center gap-2 text-sm text-gray-300">
                  <input
                    type="checkbox"
                    checked={bools[f.key] ?? false}
                    onChange={(e) => setBools({ ...bools, [f.key]: e.target.checked })}
                    className="accent-blue-600"
                  />
                  {f.label}
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
