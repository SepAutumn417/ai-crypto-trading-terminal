'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SystemStatusBadge } from './SystemStatusBadge';

const links = [
  { href: '/dashboard', label: '仪表盘' }, { href: '/market', label: '行情' }, { href: '/radar', label: '机会雷达' }, { href: '/ai', label: '指标评分' }, { href: '/plans', label: '交易计划' }, { href: '/execution', label: '执行监控' }, { href: '/journal', label: '交易日志' }, { href: '/review', label: '复盘' }, { href: '/risk', label: '风控中心', danger: true }, { href: '/settings', label: '设置' },
];

export function Navbar() {
  const path = usePathname();
  return <nav className="app-sidebar" aria-label="主导航"><Link href="/dashboard" className="app-brand"><span className="app-brand-mark">AT</span><span className="app-brand-copy">AI Trading<small>Terminal</small></span></Link><div className="app-nav"><span className="app-nav-label">Workspace</span>{links.map((link) => <Link key={link.href} href={link.href} className={`app-nav-link ${path === link.href ? 'is-active' : ''} ${link.danger ? 'is-danger' : ''}`}>{link.label}</Link>)}</div><div className="sidebar-footer"><div className="sidebar-status"><span className="status-dot" />交易保护已启用</div><SystemStatusBadge /></div></nav>;
}
