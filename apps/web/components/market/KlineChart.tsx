'use client';
import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import type { Kline } from '@/lib/api';

interface KlineChartProps {
  data: Kline[];
  height?: number;
}

interface Viewport {
  offset: number;
  visibleCount: number;
}

export function KlineChart({ data, height = 480 }: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [viewport, setViewport] = useState<Viewport>({ offset: 0, visibleCount: 60 });
  const [crosshair, setCrosshair] = useState<{ x: number; y: number; idx: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef<{ x: number; offset: number } | null>(null);

  // 响应式宽度
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setWidth(containerRef.current.clientWidth);
      }
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // 数据更新时重置 viewport 到最新
  useEffect(() => {
    if (data.length > 0) {
      const visibleCount = Math.min(60, data.length);
      setViewport({
        offset: Math.max(0, data.length - visibleCount),
        visibleCount,
      });
    }
  }, [data]);

  const padding = { top: 20, right: 70, bottom: 60, left: 10 };
  const chartWidth = width - padding.left - padding.right;
  const priceHeight = (height - padding.top - padding.bottom) * 0.7;
  const volumeHeight = (height - padding.top - padding.bottom) * 0.25;
  const gapHeight = (height - padding.top - padding.bottom) * 0.05;

  const visibleData = useMemo(() => {
    const end = Math.min(viewport.offset + viewport.visibleCount, data.length);
    return data.slice(viewport.offset, end);
  }, [data, viewport]);

  const { minPrice, maxPrice, maxVolume, candleWidth } = useMemo(() => {
    if (visibleData.length === 0) {
      return { minPrice: 0, maxPrice: 1, maxVolume: 1, candleWidth: 0 };
    }
    const prices = visibleData.flatMap(k => [parseFloat(k.high), parseFloat(k.low)]);
    const volumes = visibleData.map(k => parseFloat(k.volume));
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const range = maxP - minP || 1;
    const pad = range * 0.1;
    return {
      minPrice: minP - pad,
      maxPrice: maxP + pad,
      maxVolume: Math.max(...volumes) || 1,
      candleWidth: visibleData.length > 0 ? chartWidth / visibleData.length : 0,
    };
  }, [visibleData, chartWidth]);

  const priceToY = useCallback((price: number) => {
    const range = maxPrice - minPrice || 1;
    return padding.top + (1 - (price - minPrice) / range) * priceHeight;
  }, [minPrice, maxPrice, priceHeight, padding.top]);

  const volumeToY = useCallback((vol: number) => {
    const baseY = padding.top + priceHeight + gapHeight;
    return baseY + (1 - vol / maxVolume) * volumeHeight;
  }, [maxVolume, volumeHeight, padding.top, priceHeight, gapHeight]);

  // 鼠标交互
  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // 拖拽平移
    if (isDragging && dragStartRef.current) {
      const dx = x - dragStartRef.current.x;
      const candlesMoved = Math.round(dx / candleWidth);
      const newOffset = Math.max(0, Math.min(
        data.length - viewport.visibleCount,
        dragStartRef.current.offset - candlesMoved,
      ));
      setViewport(prev => ({ ...prev, offset: newOffset }));
      return;
    }

    // 十字线
    if (x < padding.left || x > width - padding.right) {
      setCrosshair(null);
      return;
    }
    const idx = Math.floor((x - padding.left) / candleWidth);
    if (idx >= 0 && idx < visibleData.length) {
      setCrosshair({ x, y, idx });
    } else {
      setCrosshair(null);
    }
  }, [isDragging, candleWidth, data.length, viewport.visibleCount, padding.left, padding.right, width, visibleData]);

  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    dragStartRef.current = { x: e.clientX - rect.left, offset: viewport.offset };
    setIsDragging(true);
  }, [viewport.offset]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  const handleMouseLeave = useCallback(() => {
    setCrosshair(null);
    setIsDragging(false);
    dragStartRef.current = null;
  }, []);

  // 滚轮缩放
  const handleWheel = useCallback((e: React.WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 10 : -10;
    setViewport(prev => ({
      ...prev,
      visibleCount: Math.max(20, Math.min(200, prev.visibleCount + delta)),
    }));
  }, []);

  // 键盘导航
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      setViewport(prev => ({ ...prev, offset: Math.max(0, prev.offset - 5) }));
    } else if (e.key === 'ArrowRight') {
      setViewport(prev => ({
        ...prev,
        offset: Math.min(data.length - prev.visibleCount, prev.offset + 5),
      }));
    } else if (e.key === '+' || e.key === '=') {
      setViewport(prev => ({ ...prev, visibleCount: Math.max(20, prev.visibleCount - 10) }));
    } else if (e.key === '-') {
      setViewport(prev => ({ ...prev, visibleCount: Math.min(200, prev.visibleCount + 10) }));
    }
  }, [data.length]);

  if (data.length === 0) {
    return <div className="text-gray-500 text-center py-12">暂无数据</div>;
  }

  const priceTicks = 6;
  const priceStep = (maxPrice - minPrice) / (priceTicks - 1);
  const volumeTicks = 3;
  const volStep = maxVolume / (volumeTicks - 1);

  const crosshairKline = crosshair ? visibleData[crosshair.idx] : null;

  return (
    <div ref={containerRef} className="w-full" role="img" aria-label="K线图">
      <svg
        width={width}
        height={height}
        className="bg-gray-900 rounded-lg cursor-grab active:cursor-grabbing"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        {/* 价格网格 */}
        {Array.from({ length: priceTicks }).map((_, i) => {
          const price = minPrice + priceStep * i;
          const y = priceToY(price);
          return (
            <g key={`p${i}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#1f2937" strokeDasharray="2 4" />
              <text x={width - padding.right + 5} y={y + 4} fill="#6b7280" fontSize="10" fontFamily="monospace">
                {price.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* 成交量网格 */}
        {Array.from({ length: volumeTicks }).map((_, i) => {
          const vol = volStep * i;
          const y = padding.top + priceHeight + gapHeight + (1 - i / (volumeTicks - 1)) * volumeHeight;
          return (
            <g key={`v${i}`}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke="#1f2937" strokeDasharray="1 3" />
              <text x={width - padding.right + 5} y={y + 4} fill="#6b7280" fontSize="9" fontFamily="monospace">
                {vol >= 1000 ? `${(vol / 1000).toFixed(1)}K` : vol.toFixed(0)}
              </text>
            </g>
          );
        })}

        {/* 价格/成交量分隔线 */}
        <line
          x1={padding.left}
          y1={padding.top + priceHeight + gapHeight / 2}
          x2={width - padding.right}
          y2={padding.top + priceHeight + gapHeight / 2}
          stroke="#374151"
        />

        {/* 蜡烛图 + 成交量 */}
        {visibleData.map((k, i) => {
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
          const volBottom = padding.top + priceHeight + gapHeight + volumeHeight;

          return (
            <g key={i}>
              <line x1={x} y1={wickTop} x2={x} y2={wickBottom} stroke={color} strokeWidth={1} />
              <rect
                x={x - candleWidth * 0.35}
                y={bodyTop}
                width={Math.max(candleWidth * 0.7, 1)}
                height={bodyHeight}
                fill={color}
              />
              <rect
                x={x - candleWidth * 0.35}
                y={volY}
                width={Math.max(candleWidth * 0.7, 1)}
                height={volBottom - volY}
                fill={color}
                opacity={0.4}
              />
            </g>
          );
        })}

        {/* 十字线 */}
        {crosshair && crosshairKline && (
          <g pointerEvents="none">
            <line
              x1={crosshair.x}
              y1={padding.top}
              x2={crosshair.x}
              y2={height - padding.bottom}
              stroke="#6b7280"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            <line
              x1={padding.left}
              y1={crosshair.y}
              x2={width - padding.right}
              y2={crosshair.y}
              stroke="#6b7280"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            {/* 十字线价格标签 */}
            {crosshair.y < padding.top + priceHeight + gapHeight / 2 && (
              <g>
                <rect
                  x={width - padding.right + 2}
                  y={crosshair.y - 9}
                  width={padding.right - 4}
                  height={18}
                  fill="#374151"
                  rx={2}
                />
                <text
                  x={width - padding.right + 5}
                  y={crosshair.y + 4}
                  fill="#e5e7eb"
                  fontSize="10"
                  fontFamily="monospace"
                >
                  {(() => {
                    const range = maxPrice - minPrice || 1;
                    const price = maxPrice - ((crosshair.y - padding.top) / priceHeight) * range;
                    return price.toFixed(2);
                  })()}
                </text>
              </g>
            )}
          </g>
        )}

        {/* 时间轴标签 */}
        {visibleData.length > 0 && (
          <>
            {visibleData.map((k, i) => {
              if (i % Math.ceil(visibleData.length / 6) !== 0) return null;
              const x = padding.left + i * candleWidth + candleWidth / 2;
              const d = new Date(k.timestamp);
              const label = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
              return (
                <text key={`t${i}`} x={x} y={height - padding.bottom + 15} fill="#6b7280" fontSize="9" textAnchor="middle" fontFamily="monospace">
                  {label}
                </text>
              );
            })}
          </>
        )}
      </svg>

      {/* 十字线信息浮窗 */}
      {crosshair && crosshairKline && (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-400 font-mono">
          <span>时间: {new Date(crosshairKline.timestamp).toLocaleString('zh-CN')}</span>
          <span className="text-green-400">开: {crosshairKline.open}</span>
          <span className="text-red-400">高: {crosshairKline.high}</span>
          <span className="text-red-400">低: {crosshairKline.low}</span>
          <span className="text-green-400">收: {crosshairKline.close}</span>
          <span>量: {parseFloat(crosshairKline.volume).toFixed(2)}</span>
        </div>
      )}

      {/* 操作提示 */}
      <div className="mt-1 text-xs text-gray-600 flex gap-4">
        <span>滚轮: 缩放</span>
        <span>拖拽: 平移</span>
        <span>←→: 移动</span>
        <span>+/-: 缩放</span>
        <span className="ml-auto">
          显示 {viewport.offset + 1}-{Math.min(viewport.offset + viewport.visibleCount, data.length)} / 共 {data.length} 根
        </span>
      </div>
    </div>
  );
}
