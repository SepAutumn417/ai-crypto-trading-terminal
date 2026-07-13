'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export default function ExecutionPage() {
  const snapshot = useQuery({ queryKey: ['execution-monitor'], queryFn: () => api.getAccountSnapshot(), refetchInterval: 15_000 });
  const plans = useQuery({ queryKey: ['submitted-plans'], queryFn: () => api.listPlans('SUBMITTED'), refetchInterval: 15_000 });

  return <div className="space-y-6">
    <div className="flex items-center justify-between"><div><h2 className="text-2xl font-bold">执行监控</h2><p className="text-sm text-gray-400">账户订单与持仓每 15 秒只读刷新；撤单和同步请在交易计划详情中操作。</p></div><button onClick={() => { snapshot.refetch(); plans.refetch(); }} className="rounded bg-blue-600 px-4 py-2">立即刷新</button></div>
    {snapshot.isError && <p className="rounded border border-red-800 bg-red-950/30 p-3 text-sm text-red-300">交易所同步失败：{(snapshot.error as Error).message}</p>}
    <section className="rounded border border-gray-800 bg-gray-900 p-4"><h3 className="mb-3 font-semibold">当前持仓</h3><DataTable headers={['标的', '方向', '数量', '标记价', '未实现盈亏', '强平价']} rows={(snapshot.data?.positions ?? []).map((position) => [position.symbol, position.side, position.quantity, position.mark_price ?? '-', position.unrealized_pnl ?? '-', position.liquidation_price ?? '-'])} empty="暂无持仓" /></section>
    <section className="rounded border border-gray-800 bg-gray-900 p-4"><h3 className="mb-3 font-semibold">交易所订单</h3><DataTable headers={['订单 ID', '方向', '类型', '价格', '数量', '已成交', '状态']} rows={(snapshot.data?.orders ?? []).map((order) => [order.id, order.side, order.type, order.price ?? '市价', order.quantity, order.filled_quantity, order.status])} empty="暂无订单" /></section>
    <section className="rounded border border-gray-800 bg-gray-900 p-4"><h3 className="mb-3 font-semibold">本地已提交计划</h3><DataTable headers={['标的', '方向', '订单 ID', '状态', '已成交数量']} rows={(plans.data ?? []).map((plan) => [plan.symbol, plan.direction, plan.exchange_order_id ?? '-', plan.status, plan.filled_quantity ?? '-'])} empty="暂无已提交计划" /></section>
  </div>;
}

function DataTable({ headers, rows, empty }: { headers: string[]; rows: string[][]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-gray-500">{empty}</p>;
  return <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-gray-400"><tr>{headers.map((header) => <th key={header} className="pb-2 pr-4">{header}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${row[0]}-${index}`} className="border-t border-gray-800">{row.map((value, cell) => <td key={cell} className="py-2 pr-4">{value}</td>)}</tr>)}</tbody></table></div>;
}
