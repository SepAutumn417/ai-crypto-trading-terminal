'use client';

import { OpportunityRadar } from '@/components/radar/OpportunityRadar';

export default function RadarPage() {
  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">机会雷达</h1>
      <OpportunityRadar />
    </div>
  );
}
