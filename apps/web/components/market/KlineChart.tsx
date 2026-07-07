'use client';
import { useMemo } from 'react';
import { Kline } from '@/lib/api';

interface KlineChartProps {
  data: Kline[];
  height?: number;
}

export function KlineChart({ data, height = 400 }: KlineChartProps) {
  const width = 800;
  const padding = { top: 20, right: 60, bottom: 40, left: 20 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;
  const volumeHeight = 80;
  const priceHeight = chartHeight - volumeHeight - 10;

  const { minPrice, maxPrice, maxVolume, candleWidth } = useMemo(() => {
    if (data.length === 0) {
      return { minPrice: 0, maxPrice: 1, maxVolume: 1, candleWidth: 0 };
    }
    const prices = data.flatMap(k => [parseFloat(k.high), parseFloat(k.low)]);
    const volumes = data.map(k => parseFloat(k.volume));
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const maxVolume = Math.max(...volumes) || 1;
    const candleWidth = data.length > 0 ? chartWidth / data.length : 0;
    const priceRange = maxPrice - minPrice;
    const padding = priceRange * 0.1;
    return {
      minPrice: minPrice - padding,
      maxPrice: maxPrice + padding,
      maxVolume,
      candleWidth,
    };
  }, [data, chartWidth]);

  const priceToY = (price: number) => {
    const range = maxPrice - minPrice;
    return padding.top + (1 - (price - minPrice) / range) * priceHeight;
  };

  const volumeToY = (vol: number) => {
    return padding.top + priceHeight + 10 + (1 - vol / maxVolume) * volumeHeight;
  };

  if (data.length === 0) {
    return <div className="text-gray-500 text-center py-12">暂无数据</div>;
  }

  const priceTicks = 5;
  const priceStep = (maxPrice - minPrice) / (priceTicks - 1);

  return (
    <div className="w-full overflow-x-auto">
      <svg width={width} height={height} className="bg-gray-900 rounded-lg">
        {Array.from({ length: priceTicks }).map((_, i) => {
          const price = minPrice + priceStep * i;
          const y = priceToY(price);
          return (
            <g key={i}>
              <line
              x1={padding.left}
              y1={y}
              x2={width - padding.right}
              y2={y}
              stroke="#374151"
              strokeDasharray="2 4"
            />
            <text
              x={width - padding.right + 5}
              y={y + 4}
              fill="#9ca3af"
              fontSize="10"
            >
              {price.toFixed(2)}
            </text>
          </g>
        );
        })}

        <line
          x1={padding.left}
          y1={padding.top + priceHeight + 10}
          x2={width - padding.right}
          y2={padding.top + priceHeight + 10}
          stroke="#374151"
        />

        {data.map((k, i) => {
          const x = padding.left + i * candleWidth + candleWidth / 2;
          const open = parseFloat(k.open);
          const close = parseFloat(k.close);
          const high = parseFloat(k.high);
          const low = parseFloat(k.low);
          const vol = parseFloat(k.volume);
          const isUp = close >= open;
          const color = isUp ? '#10b981' : '#ef4444';
          const bodyTop = priceToY(Math.max(open, close));
          const bodyBottom = priceToY(Math.min(open, close));
          const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
          const wickTop = priceToY(high);
          const wickBottom = priceToY(low);
          const volY = volumeToY(vol);
          const volBottom = padding.top + priceHeight + 10 + volumeHeight;

          return (
            <g key={i}>
              <line
                x1={x}
                y1={wickTop}
                x2={x}
                y2={wickBottom}
                stroke={color}
                strokeWidth={1}
              />
              <rect
                x={x - candleWidth * 0.35}
                y={bodyTop}
                width={candleWidth * 0.7}
                height={bodyHeight}
                fill={color}
              />
              <rect
                x={x - candleWidth * 0.35}
                y={volY}
                width={candleWidth * 0.7}
                height={volBottom - volY}
                fill={color}
                opacity={0.5}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
