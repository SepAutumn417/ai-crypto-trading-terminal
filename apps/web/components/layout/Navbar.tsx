'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SystemStatusBadge } from './SystemStatusBadge';

export function Navbar() {
  const path = usePathname();
  const links = [
    { href: '/dashboard', label: '仪表盘' },
    { href: '/market', label: '行情' },
    { href: '/radar', label: '机会雷达' },
    { href: '/ai', label: '指标评分' },
    { href: '/plans', label: '交易计划' },
    { href: '/execution', label: '执行监控' },
    { href: '/journal', label: '交易日志' },
    { href: '/review', label: '复盘' },
    { href: '/risk', label: '风控中心' },
    { href: '/settings', label: '设置' },
  ];
  return (
    <nav className="border-b border-gray-800 bg-gray-950">
      <div className="container mx-auto px-4 py-3 flex items-center gap-6">
        <h1 className="text-lg font-bold">AI Trading Terminal</h1>
        <div className="flex gap-4">
          {links.map((l) => (
            <Link key={l.href} href={l.href}
              className={`px-3 py-1 rounded ${path === l.href ? 'bg-blue-600' : 'hover:bg-gray-800'}`}>
              {l.label}
            </Link>
          ))}
        </div>
        <div className="ml-auto">
          <SystemStatusBadge />
        </div>
      </div>
    </nav>
  );
}
