"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType } from "lightweight-charts";

interface EquityPoint {
  date: string;
  value: number;
}

export interface CompareSeriesConfig {
  id: string;
  name: string;
  color: string;
  data: EquityPoint[];
}

interface Props {
  series: CompareSeriesConfig[];
  height?: number;
}

export default function CompareEquityChart({ series, height = 280 }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || series.length === 0) return;

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#64748b",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      width: chartRef.current.clientWidth,
      height,
      timeScale: { borderColor: "rgba(255,255,255,0.1)" },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
    });

    for (const s of series) {
      if (!s.data?.length) continue;
      const line = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        crosshairMarkerVisible: false,
        priceLineVisible: false,
        lastValueVisible: false,
        title: "",
      });
      line.setData(s.data.map((d) => ({ time: d.date, value: d.value })));
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [series, height]);

  return <div ref={chartRef} className="w-full" />;
}
