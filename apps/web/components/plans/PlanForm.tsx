'use client';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { PlanCreate } from '@/lib/api';

const schema = z.object({
  symbol: z.string().min(1),
  direction: z.enum(['LONG', 'SHORT']),
  entry_price: z.string(),
  stop_loss_price: z.string().optional(),
  take_profit_prices: z.string(),
  leverage: z.string(),
  risk_percent: z.string(),
  opportunity_grade: z.enum(['A', 'B', 'C', 'BLOCKED']),
  equity: z.string(),
  margin_mode: z.enum(['isolated', 'crossed']),
  setup_type: z.string().optional(),
  notes: z.string().optional(),
});

export function PlanForm({ onSubmit, submitting }: { onSubmit: (v: PlanCreate) => void; submitting: boolean }) {
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      symbol: 'BTCUSDT', direction: 'LONG', entry_price: '62400', stop_loss_price: '61900',
      take_profit_prices: '63800,64500', leverage: '10', risk_percent: '1',
      opportunity_grade: 'A', equity: '1500',
      margin_mode: 'isolated', setup_type: '', notes: '',
    },
  });

  return (
    <form onSubmit={handleSubmit((data) => onSubmit({
      symbol: data.symbol,
      direction: data.direction as 'LONG' | 'SHORT',
      entry_price: data.entry_price,
      stop_loss_price: data.stop_loss_price,
      take_profit_prices: data.take_profit_prices.split(',').map((s) => s.trim()).filter(Boolean),
      leverage: data.leverage,
      risk_percent: data.risk_percent,
      opportunity_grade: data.opportunity_grade as 'A' | 'B' | 'C' | 'BLOCKED',
      equity: data.equity,
      margin_mode: data.margin_mode,
      setup_type: data.setup_type || undefined,
      notes: data.notes || undefined,
    }))}
      className="space-y-2 p-4 border border-gray-800 rounded">
      <div className="grid grid-cols-2 gap-2">
        <label className="text-sm">交易对
          <input {...register('symbol')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">方向
          <select {...register('direction')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded">
            <option value="LONG">做多</option>
            <option value="SHORT">做空</option>
          </select>
        </label>
        <label className="text-sm">入场价
          <input {...register('entry_price')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">止损价
          <input {...register('stop_loss_price')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm col-span-2">止盈价（逗号分隔）
          <input {...register('take_profit_prices')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">杠杆
          <input {...register('leverage')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">风险%
          <input {...register('risk_percent')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">等级
          <select {...register('opportunity_grade')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded">
            <option value="A">A</option><option value="B">B</option>
            <option value="C">C</option><option value="BLOCKED">BLOCKED</option>
          </select>
        </label>
        <label className="text-sm">保证金模式
          <select {...register('margin_mode')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded">
            <option value="isolated">逐仓</option>
            <option value="crossed">全仓</option>
          </select>
        </label>
        <label className="text-sm">账户权益
          <input {...register('equity')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm">形态类型
          <input {...register('setup_type')} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded" />
        </label>
        <label className="text-sm col-span-2">备注
          <textarea {...register('notes')} rows={2} className="block w-full bg-gray-900 border border-gray-700 px-2 py-1 rounded resize-none" />
        </label>
      </div>
      <button type="submit" disabled={submitting}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 px-3 py-2 rounded">
        {submitting ? '创建中...' : '创建计划'}
      </button>
    </form>
  );
}