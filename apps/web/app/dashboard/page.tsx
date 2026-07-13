'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

export default function DashboardPage() {
  const { data: status } = useQuery({ queryKey: ['system-status'], queryFn: api.getSystemStatus, refetchInterval: 15_000 });
  const account = useQuery({ queryKey: ['account-snapshot'], queryFn: () => api.getAccountSnapshot(), refetchInterval: 30_000 });
  const snapshot = account.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">交易仪表盘</h2>
          <p className="text-sm text-gray-400">只读账户同步不会提交或修改任何交易所订单。</p>
        </div>
        <button className="rounded bg-blue-600 px-4 py-2 disabled:bg-gray-700" onClick={() => account.refetch()} disabled={account.isFetching}>
          {account.isFetching ? '同步中...' : '刷新账户'}
        </button>
      </div>
      {account.isError && <p className="rounded border border-red-800 bg-red-950/30 p-3 text-sm text-red-300">账户同步失败：{(account.error as Error).message}</p>}
      <div className="grid gap-4 md:grid-cols-3">
        <Stat label="执行模式" value={status?.execution_enabled ? '已开启' : '已关闭'} tone={status?.execution_enabled ? 'text-green-400' : 'text-gray-400'} />
        <Stat label="Kill Switch" value={status?.kill_switch ? '已激活' : '未激活'} tone={status?.kill_switch ? 'text-red-400' : 'text-green-400'} />
        <Stat label="账户权益" value={snapshot?.balances[0]?.equity ?? '-'} tone="text-white" />
      </div>
      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <h3 className="mb-3 font-semibold">持仓</h3>
        {snapshot?.positions.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-gray-400"><tr><th>标的</th><th>方向</th><th>数量</th><th>开仓价</th><th>未实现盈亏</th><th>杠杆</th></tr></thead><tbody>{snapshot.positions.map((position) => <tr key={`${position.symbol}-${position.side}`} className="border-t border-gray-800"><td>{position.symbol}</td><td>{position.side}</td><td>{position.quantity}</td><td>{position.entry_price}</td><td>{position.unrealized_pnl ?? '-'}</td><td>{position.leverage}x</td></tr>)}</tbody></table></div> : <p className="text-sm text-gray-500">暂无持仓</p>}
      </section>
      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <h3 className="mb-3 font-semibold">最近订单（{snapshot?.symbol ?? 'BTCUSDT'}）</h3>
        {snapshot?.orders.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-gray-400"><tr><th>订单 ID</th><th>方向</th><th>类型</th><th>价格</th><th>数量</th><th>状态</th></tr></thead><tbody>{snapshot.orders.map((order) => <tr key={order.id} className="border-t border-gray-800"><td>{order.id}</td><td>{order.side}</td><td>{order.type}</td><td>{order.price ?? '市价'}</td><td>{order.quantity}</td><td>{order.status}</td></tr>)}</tbody></table></div> : <p className="text-sm text-gray-500">暂无订单</p>}
      </section>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className="rounded border border-gray-800 bg-gray-900 p-4"><p className="text-sm text-gray-400">{label}</p><p className={`mt-1 text-xl font-semibold ${tone}`}>{value}</p></div>;
}
