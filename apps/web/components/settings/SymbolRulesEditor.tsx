'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type ConfigVersion, type CreateConfigInput } from '@/lib/api';

interface SymbolRule {
  size_step: number;
  price_step: number;
  min_size: number;
  min_notional: number;
  max_leverage: number;
  fee_rate: number;
}

interface SymbolRulesPayload {
  rules: Record<string, SymbolRule>;
}

const RULE_FIELDS: { key: keyof SymbolRule; label: string }[] = [
  { key: 'size_step', label: 'size_step' },
  { key: 'price_step', label: 'price_step' },
  { key: 'min_size', label: 'min_size' },
  { key: 'min_notional', label: 'min_notional' },
  { key: 'max_leverage', label: 'max_leverage' },
  { key: 'fee_rate', label: 'fee_rate' },
];

export function SymbolRulesEditor({ activeConfig }: { activeConfig?: ConfigVersion | null }) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [versionLabel, setVersionLabel] = useState('');
  const [rulesJson, setRulesJson] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: (input: CreateConfigInput) => api.createConfig(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['activeConfigs'] });
      qc.invalidateQueries({ queryKey: ['configs', 'symbol_rules'] });
      setShowForm(false);
      setVersionLabel('');
      setRulesJson('');
      setFormError(null);
    },
  });

  if (!activeConfig) return null;

  const payload = activeConfig.payload as SymbolRulesPayload;
  const rules = payload.rules ?? {};
  const symbols = Object.keys(rules);

  const openForm = () => {
    setVersionLabel('');
    setRulesJson(JSON.stringify(rules, null, 2));
    setFormError(null);
    setShowForm(true);
  };

  const handleSubmit = () => {
    setFormError(null);
    if (!versionLabel.trim()) {
      setFormError('请输入版本标签');
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(rulesJson);
    } catch (e) {
      setFormError(`JSON 解析失败：${(e as Error).message}`);
      return;
    }
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      setFormError('rules 必须是 JSON 对象');
      return;
    }
    createMut.mutate({
      config_type: 'symbol_rules',
      version_label: versionLabel.trim(),
      payload: { rules: parsed },
    });
  };

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">交易对规则（{activeConfig.version_label}）</h3>
      {symbols.length === 0 ? (
        <p className="text-xs text-gray-500">暂无交易对规则</p>
      ) : (
        <div className="space-y-2">
          {symbols.map((sym) => {
            const r = rules[sym];
            return (
              <div key={sym} className="border border-gray-800 rounded p-2">
                <div className="font-mono text-sm text-gray-100 mb-1">{sym}</div>
                <dl className="grid grid-cols-3 gap-x-3 gap-y-1 text-xs">
                  {RULE_FIELDS.map((f) => (
                    <div key={f.key} className="flex justify-between">
                      <dt className="text-gray-500">{f.label}</dt>
                      <dd className="font-mono text-right text-gray-200">
                        {String(r?.[f.key] ?? '-')}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })}
        </div>
      )}

      {!showForm ? (
        <button
          onClick={openForm}
          className="mt-3 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm"
        >
          新建版本
        </button>
      ) : (
        <div className="mt-4 border-t border-gray-800 pt-4">
          <h4 className="text-sm font-bold mb-2 text-gray-200">新建交易对规则版本</h4>
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
            <label className="block">
              <span className="text-xs text-gray-500">rules（JSON 对象）</span>
              <textarea
                value={rulesJson}
                onChange={(e) => setRulesJson(e.target.value)}
                rows={10}
                placeholder='{"BTCUSDT": {"size_step": 0.001, "price_step": 0.01, "min_size": 0.001, "min_notional": 5, "max_leverage": 125, "fee_rate": 0.0006}}'
                className="block w-full bg-gray-950 border border-gray-700 px-2 py-1 rounded font-mono text-xs"
              />
            </label>
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
