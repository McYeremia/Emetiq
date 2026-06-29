"use client";

import { useEffect, useRef } from "react";
import { createChart, createSeriesMarkers, CandlestickSeries, LineSeries, ColorType } from "lightweight-charts";
import type { ChartSyncCoordinator } from "@/lib/chartSync";

interface OHLCVRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Props {
  data: OHLCVRow[];
  indicators?: Record<string, number | null>;
  showMA20?: boolean;
  showMA50?: boolean;
  showMA200?: boolean;
  showEMA12?: boolean;
  showEMA26?: boolean;
  showBB?: boolean;
  height?: number;
  transparent?: boolean;
  markerDate?: string;
  markerColor?: string;
  sync?: ChartSyncCoordinator;
}

export default function StockChart({
  data,
  indicators = {},
  showMA20 = false,
  showMA50 = false,
  showMA200 = false,
  showEMA12 = false,
  showEMA26 = false,
  showBB = false,
  height = 420,
  transparent = false,
  markerDate,
  markerColor = '#f59e0b',
  sync,
}: Props) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    const chart = createChart(chartRef.current, {
      layout: { 
        background: { 
          type: ColorType.Solid, 
          color: transparent ? "transparent" : "#0a0a0a" 
        }, 
        textColor: "#64748b" 
      },
      grid: { 
        vertLines: { color: "rgba(255, 255, 255, 0.03)" }, 
        horzLines: { color: "rgba(255, 255, 255, 0.03)" } 
      },
      width: chartRef.current.clientWidth,
      height: height,
      timeScale: { 
        borderColor: "rgba(255, 255, 255, 0.1)",
        barSpacing: 10,
      },
      rightPriceScale: { 
        borderColor: "rgba(255, 255, 255, 0.1)",
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
      },
    });

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e", 
      downColor: "#ef4444",
      borderUpColor: "#22c55e", 
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e", 
      wickDownColor: "#ef4444",
    });

    const candleData = data.map((r) => ({
      time: r.date as string,
      open: r.open, 
      high: r.high, 
      low: r.low, 
      close: r.close,
    }));
    candles.setData(candleData);

    // Trade marker (lightweight-charts v5 API)
    if (markerDate) {
      const markerExists = candleData.some(c => c.time === markerDate);
      if (markerExists) {
        const isBuy = markerColor === '#22c55e';
        createSeriesMarkers(candles, [{
          time: markerDate as any,
          position: isBuy ? 'belowBar' : 'aboveBar',
          color: markerColor,
          shape: isBuy ? 'arrowUp' : 'arrowDown',
          text: isBuy ? 'BUY' : 'SELL',
        }]);
      }
    }

    // MA20 overlay
    if (showMA20 && data.length >= 20) {
      const ma20 = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1 });
      const values: { time: string; value: number }[] = [];
      for (let i = 19; i < data.length; i++) {
        const avg = data.slice(i - 19, i + 1).reduce((s, r) => s + r.close, 0) / 20;
        values.push({ time: data[i].date, value: avg });
      }
      ma20.setData(values);
    }

    // MA50 overlay
    if (showMA50 && data.length >= 50) {
      const ma50 = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 1 });
      const values: { time: string; value: number }[] = [];
      for (let i = 49; i < data.length; i++) {
        const avg = data.slice(i - 49, i + 1).reduce((s, r) => s + r.close, 0) / 50;
        values.push({ time: data[i].date, value: avg });
      }
      ma50.setData(values);
    }

    // EMA12 overlay
    if (showEMA12 && data.length >= 12) {
      const ema12 = chart.addSeries(LineSeries, { color: "#38bdf8", lineWidth: 1 });
      const k = 2 / (12 + 1);
      let ema = data[0].close;
      const values: { time: string; value: number }[] = [];
      data.forEach((r) => {
        ema = r.close * k + ema * (1 - k);
        values.push({ time: r.date, value: ema });
      });
      ema12.setData(values);
    }

    // EMA26 overlay
    if (showEMA26 && data.length >= 26) {
      const ema26Series = chart.addSeries(LineSeries, { color: "#22d3ee", lineWidth: 1 });
      const k = 2 / (26 + 1);
      let ema = data[0].close;
      const values: { time: string; value: number }[] = [];
      data.forEach((r) => {
        ema = r.close * k + ema * (1 - k);
        values.push({ time: r.date, value: ema });
      });
      ema26Series.setData(values);
    }

    // MA200 overlay
    if (showMA200 && data.length >= 200) {
      const ma200 = chart.addSeries(LineSeries, { color: "#f97316", lineWidth: 1 });
      const values: { time: string; value: number }[] = [];
      for (let i = 199; i < data.length; i++) {
        const avg = data.slice(i - 199, i + 1).reduce((s, r) => s + r.close, 0) / 200;
        values.push({ time: data[i].date, value: avg });
      }
      ma200.setData(values);
    }

    // Bollinger Bands overlay
    if (showBB && data.length >= 20) {
      const bbUpper = chart.addSeries(LineSeries, { color: "rgba(236,72,153,0.65)", lineWidth: 1 });
      const bbMid   = chart.addSeries(LineSeries, { color: "rgba(236,72,153,0.3)",  lineWidth: 1 });
      const bbLower = chart.addSeries(LineSeries, { color: "rgba(236,72,153,0.65)", lineWidth: 1 });
      const upper: { time: string; value: number }[] = [];
      const mid:   { time: string; value: number }[] = [];
      const lower: { time: string; value: number }[] = [];
      for (let i = 19; i < data.length; i++) {
        const slice = data.slice(i - 19, i + 1).map(r => r.close);
        const mean  = slice.reduce((s, v) => s + v, 0) / 20;
        const std   = Math.sqrt(slice.reduce((s, v) => s + (v - mean) ** 2, 0) / 20);
        upper.push({ time: data[i].date, value: mean + 2 * std });
        mid.push(  { time: data[i].date, value: mean });
        lower.push({ time: data[i].date, value: mean - 2 * std });
      }
      bbUpper.setData(upper);
      bbMid.setData(mid);
      bbLower.setData(lower);
    }

    chart.timeScale().fitContent();

    // Sync by visible TIME range (not bar index) so charts with different
    // data lengths (RSI starts at bar 14, MACD at bar 25, etc.) stay aligned.
    let unregisterSync: (() => void) | undefined;
    if (sync) {
      unregisterSync = sync.register('price', (from, to) => {
        chart.timeScale().setVisibleRange({ from, to } as any);
      });
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range) sync.notify('price', range.from, range.to);
      });
    }

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      unregisterSync?.();
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, showMA20, showMA50, showMA200, showEMA12, showEMA26, showBB, height, transparent, markerDate, markerColor, sync]);

  return <div ref={chartRef} className="w-full" />;
}
