'use client';
import type { MarketStructureSnapshot, SwingPoint, PriceZone } from '@/lib/api';

const stateColors: Record<string, string> = {
  trend: 'text-green-400',
  range: 'text-yellow-400',
  transition: 'text-orange-400',
};

const trendColors: Record<string, string> = {
  bullish: 'text-green-400',
  bearish: 'text-red-400',
  neutral: 'text-gray-400',
};

const stateLabels: Record<string, string> = {
  trend: '趋势',
  range: '震荡',
  transition: '转换中',
};

const trendLabels: Record<string, string> = {
  bullish: '看涨',
  bearish: '看跌',
  neutral: '中性',
};

function ZoneRow({ zone }: { zone: PriceZone }) {
  const colorMap: Record<string, string> = {
    support: 'text-green-400',
    resistance: 'text-red-400',
    no_trade: 'text-orange-400',
  };
  const labelMap: Record<string, string> = {
    support: '支撑',
    resistance: '阻力',
    no_trade: '禁交易',
  };
  return (
    <div className="flex items-center justify-between text-xs py-1 border-b border-gray-800">
      <span className={colorMap[zone.zone_type]}>
        {labelMap[zone.zone_type]} x{zone.strength}
      </span>
      <span className="text-gray-300">
        {zone.lower} ~ {zone.upper}
      </span>
    </div>
  );
}

function SwingList({ swings, label }: { swings: SwingPoint[]; label: string }) {
  if (swings.length === 0) return null;
  const recent = swings.slice(-5).reverse();
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label}（最近 {recent.length} 个）</div>
      <div className="space-y-1">
        {recent.map((s) => (
          <div key={s.id} className="flex items-center justify-between text-xs">
            <span className={`font-mono ${s.type === 'high' ? 'text-red-400' : 'text-green-400'}`}>
              {s.structure_label || s.type.toUpperCase()}
            </span>
            <span className="text-gray-300">{s.price}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function StructurePanel({ snapshot }: { snapshot: MarketStructureSnapshot | null }) {
  if (!snapshot) {
    return (
      <div className="p-4 border border-gray-800 rounded">
        <h3 className="text-lg font-bold mb-2">市场结构</h3>
        <p className="text-gray-500 text-sm">加载中...</p>
      </div>
    );
  }

  return (
    <div className="p-4 border border-gray-800 rounded space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold">市场结构</h3>
        <span className="text-xs text-gray-500">{snapshot.timeframe}</span>
      </div>

      {/* 市场状态 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-xs text-gray-500">市场状态</div>
          <div className={`text-lg font-bold ${stateColors[snapshot.market_state]}`}>
            {stateLabels[snapshot.market_state]}
          </div>
        </div>
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-xs text-gray-500">趋势方向</div>
          <div className={`text-lg font-bold ${trendColors[snapshot.trend_direction]}`}>
            {trendLabels[snapshot.trend_direction]}
          </div>
        </div>
      </div>

      {/* 波动率 + BOS/CHOCH 统计 */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-xs text-gray-500">波动率</div>
          <div className="text-sm font-bold">
            {snapshot.volatility_state === 'low' ? '低' : snapshot.volatility_state === 'high' ? '高' : '正常'}
          </div>
        </div>
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-xs text-gray-500">BOS</div>
          <div className="text-sm font-bold text-blue-400">{snapshot.bos_events.length}</div>
        </div>
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-xs text-gray-500">CHOCH</div>
          <div className="text-sm font-bold text-orange-400">{snapshot.choch_events.length}</div>
        </div>
      </div>

      {/* 支撑/阻力区 */}
      {snapshot.support_zones.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1">支撑/阻力区</div>
          {[...snapshot.resistance_zones].reverse().map((z) => (
            <ZoneRow key={z.id} zone={z} />
          ))}
          {snapshot.support_zones.map((z) => (
            <ZoneRow key={z.id} zone={z} />
          ))}
        </div>
      )}

      {/* 禁交易区 */}
      {snapshot.no_trade_zones.length > 0 && (
        <div className="p-2 bg-orange-900/20 border border-orange-800 rounded">
          <div className="text-xs text-orange-400 font-bold">禁交易区域</div>
          {snapshot.no_trade_zones.map((z) => (
            <div key={z.id} className="text-xs text-gray-300">
              {z.lower} ~ {z.upper}
            </div>
          ))}
        </div>
      )}

      {/* Swing 点 */}
      <div className="grid grid-cols-2 gap-2">
        <SwingList swings={snapshot.swing_highs} label="Swing High" />
        <SwingList swings={snapshot.swing_lows} label="Swing Low" />
      </div>
    </div>
  );
}
