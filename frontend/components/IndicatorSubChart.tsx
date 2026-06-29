"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, HistogramSeries, ColorType } from "lightweight-charts";
import type { ChartSyncCoordinator } from "@/lib/chartSync";

interface OHLCVRow {
  date: string; open: number; high: number; low: number; close: number; volume: number;
}

export type SubPanelType = 'rsi' | 'macd' | 'stoch' | 'volume';

interface Props {
  data: OHLCVRow[];
  type: SubPanelType;
  sync?: ChartSyncCoordinator;
}

function calcRSI(data: OHLCVRow[], period = 14) {
  const result: { time: string; value: number }[] = [];
  if (data.length <= period) return result;
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const d = data[i].close - data[i - 1].close;
    avgGain += Math.max(d, 0);
    avgLoss += Math.max(-d, 0);
  }
  avgGain /= period;
  avgLoss /= period;
  for (let i = period; i < data.length; i++) {
    if (i > period) {
      const d = data[i].close - data[i - 1].close;
      avgGain = (avgGain * (period - 1) + Math.max(d, 0)) / period;
      avgLoss = (avgLoss * (period - 1) + Math.max(-d, 0)) / period;
    }
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    result.push({ time: data[i].date, value: rsi });
  }
  return result;
}

function calcEMAArr(values: number[], period: number) {
  const k = 2 / (period + 1);
  let ema = values[0];
  return values.map(v => { ema = v * k + ema * (1 - k); return ema; });
}

function calcMACD(data: OHLCVRow[]) {
  if (data.length < 35) return { macdLine: [], signalLine: [] };
  const closes = data.map(r => r.close);
  const ema12 = calcEMAArr(closes, 12);
  const ema26 = calcEMAArr(closes, 26);
  const macdRaw = ema12.map((v, i) => v - ema26[i]);
  const signalRaw = calcEMAArr(macdRaw.slice(25), 9);
  const macdLine: { time: string; value: number }[] = [];
  const signalLine: { time: string; value: number }[] = [];
  for (let i = 25; i < data.length; i++) macdLine.push({ time: data[i].date, value: macdRaw[i] });
  for (let i = 0; i < signalRaw.length; i++) signalLine.push({ time: data[i + 25].date, value: signalRaw[i] });
  return { macdLine, signalLine };
}

function calcStoch(data: OHLCVRow[], period = 14) {
  const kSeries: { time: string; value: number }[] = [];
  const dSeries: { time: string; value: number }[] = [];
  const kValues: number[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const slice = data.slice(i - period + 1, i + 1);
    const lo = Math.min(...slice.map(r => r.low));
    const hi = Math.max(...slice.map(r => r.high));
    const k = hi === lo ? 50 : ((data[i].close - lo) / (hi - lo)) * 100;
    kValues.push(k);
    kSeries.push({ time: data[i].date, value: k });
  }
  for (let i = 2; i < kValues.length; i++) {
    dSeries.push({ time: data[i + period - 1].date, value: (kValues[i] + kValues[i - 1] + kValues[i - 2]) / 3 });
  }
  return { kSeries, dSeries };
}

function getVolumeData(data: OHLCVRow[]) {
  return data.map(r => ({
    time: r.date,
    value: r.volume,
    color: r.close >= r.open ? 'rgba(34,197,94,0.55)' : 'rgba(239,68,68,0.55)',
  }));
}

function calcVolumeMA(data: OHLCVRow[], period = 20) {
  const result: { time: string; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    const avg = data.slice(i - period + 1, i + 1).reduce((s, r) => s + r.volume, 0) / period;
    result.push({ time: data[i].date, value: avg });
  }
  return result;
}

const LABELS: Record<SubPanelType, string> = {
  rsi: 'RSI (14)',
  macd: 'MACD (12,26,9)',
  stoch: 'Stochastic (14,3)',
  volume: 'Volume',
};

const LEGENDS: Record<SubPanelType, { label: string; color: string }[]> = {
  rsi:    [{ label: 'RSI', color: '#f59e0b' }, { label: 'Oversold 30', color: 'rgba(34,197,94,0.5)' }, { label: 'Overbought 70', color: 'rgba(239,68,68,0.5)' }],
  macd:   [{ label: 'MACD', color: '#60a5fa' }, { label: 'Signal', color: '#f87171' }],
  stoch:  [{ label: '%K', color: '#34d399' }, { label: '%D', color: '#f59e0b' }],
  volume: [{ label: 'Vol Bar', color: 'rgba(34,197,94,0.55)' }, { label: 'MA 20', color: '#f59e0b' }],
};

export default function IndicatorSubChart({ data, type, sync }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.02)' },
        horzLines: { color: 'rgba(255,255,255,0.02)' },
      },
      width: chartRef.current.clientWidth,
      height: 130,
      timeScale: { borderColor: 'rgba(255,255,255,0.05)', visible: false },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.05)' },
      handleScale: { mouseWheel: true, pinch: true },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
    });

    if (type === 'rsi') {
      const values = calcRSI(data);
      if (values.length > 0) {
        const series = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1 });
        series.setData(values);
        series.createPriceLine({ price: 70, color: 'rgba(239,68,68,0.45)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
        series.createPriceLine({ price: 30, color: 'rgba(34,197,94,0.45)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
        series.createPriceLine({ price: 50, color: 'rgba(255,255,255,0.08)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
      }
    } else if (type === 'macd') {
      const { macdLine, signalLine } = calcMACD(data);
      if (macdLine.length > 0) {
        const macd = chart.addSeries(LineSeries, { color: '#60a5fa', lineWidth: 1 });
        const signal = chart.addSeries(LineSeries, { color: '#f87171', lineWidth: 1 });
        macd.setData(macdLine);
        signal.setData(signalLine);
        macd.createPriceLine({ price: 0, color: 'rgba(255,255,255,0.12)', lineWidth: 1, lineStyle: 0, axisLabelVisible: false, title: '' });
      }
    } else if (type === 'stoch') {
      const { kSeries, dSeries } = calcStoch(data);
      if (kSeries.length > 0) {
        const k = chart.addSeries(LineSeries, { color: '#34d399', lineWidth: 1 });
        const d = chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1 });
        k.setData(kSeries);
        d.setData(dSeries);
        k.createPriceLine({ price: 80, color: 'rgba(239,68,68,0.45)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
        k.createPriceLine({ price: 20, color: 'rgba(34,197,94,0.45)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' });
      }
    } else if (type === 'volume') {
      const volBars = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'vol',
      });
      chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } });
      volBars.setData(getVolumeData(data));

      const vma = calcVolumeMA(data, 20);
      if (vma.length > 0) {
        const vmaLine = chart.addSeries(LineSeries, {
          color: '#f59e0b',
          lineWidth: 1,
          priceScaleId: 'vol',
        });
        vmaLine.setData(vma);
      }
    }

    chart.timeScale().fitContent();

    // Sync by visible TIME range so this panel stays aligned with the price chart
    // even though it has fewer data points (RSI starts bar 14, MACD bar 25, etc.)
    let unregisterSync: (() => void) | undefined;
    if (sync) {
      unregisterSync = sync.register('indicator', (from, to) => {
        chart.timeScale().setVisibleRange({ from, to } as any);
      });
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (range) sync.notify('indicator', range.from, range.to);
      });
    }

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener('resize', handleResize);
    return () => {
      unregisterSync?.();
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, type, sync]);

  return (
    <div className="border-t border-white/5 px-6 pt-3 pb-2">
      <div className="flex items-center gap-4 mb-2">
        <p className="text-[8px] font-black text-gray-500 uppercase tracking-widest">{LABELS[type]}</p>
        <div className="flex items-center gap-3">
          {LEGENDS[type].map(l => (
            <span key={l.label} className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 inline-block rounded" style={{ backgroundColor: l.color }} />
              <span className="text-[7px] font-mono text-gray-600">{l.label}</span>
            </span>
          ))}
        </div>
      </div>
      <div ref={chartRef} className="w-full" />
    </div>
  );
}
