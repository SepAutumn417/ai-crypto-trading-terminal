'use client';
import { OpportunityRadar } from '@/components/radar/OpportunityRadar';

export default function RadarPage() {
  return <div className="page-stack"><header className="page-header"><div><p className="eyebrow">发现与筛选</p><h1 className="page-title">机会雷达</h1><p className="page-subtitle">按交易对和周期扫描候选信号，优先处理可进入风险校验的高质量机会。</p></div></header><OpportunityRadar /></div>;
}
