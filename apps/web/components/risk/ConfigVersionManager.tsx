'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

const TYPES = ['risk', 'execution', 'opportunity_grade', 'symbol_rules'] as const;

export function ConfigVersionManager() {
  const [tab, setTab] = useState<typeof TYPES[number]>('risk');
  const qc = useQueryClient();
  const { data: versions = [] } = useQuery({
    queryKey: ['configs', tab],
    queryFn: () => api.listConfigs(tab),
  });
  const activateMut = useMutation({
    mutationFn: (id: string) => api.activateConfig(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['configs', tab] });
      qc.invalidateQueries({ queryKey: ['activeConfigs'] });
    },
  });

  return (
    <div className="p-4 border border-gray-800 rounded">
      <h3 className="font-bold mb-2">配置版本管理</h3>
      <div className="flex gap-2 mb-3 border-b border-gray-800">
        {TYPES.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-3 py-1 text-sm ${tab === t ? 'border-b-2 border-blue-500' : 'text-gray-500'}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="space-y-2">
        {versions.map((v) => (
          <div key={v.id} className={`p-2 border rounded ${v.is_active ? 'border-green-500 bg-green-950' : 'border-gray-800'}`}>
            <div className="flex justify-between items-center">
              <span className="font-mono text-sm">{v.version_label}</span>
              {v.is_active ? (
                <span className="text-xs text-green-400">ACTIVE</span>
              ) : (
                <button onClick={() => activateMut.mutate(v.id)}
                  className="text-xs px-2 py-1 border border-gray-700 rounded hover:bg-gray-800">
                  激活
                </button>
              )}
            </div>
            <div className="text-xs text-gray-500 mt-1">{v.created_at}</div>
          </div>
        ))}
      </div>
    </div>
  );
}