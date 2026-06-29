"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType } from "lightweight-charts";

interface EquityPoint {
  date: string;
  value: number;
}

interface Props {
  data: EquityPoint[];
  color?: string;
  height?: number;
}

export default function EquityChart({ data, color = "#3b82f6", height = 300 }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || data.length === 0) return;

    const chart = createChart(chartRef.current, {
      layout: { 
        background: { type: ColorType.Solid, color: "transparent" }, 
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
      },
      rightPriceScale: { 
        borderColor: "rgba(255, 255, 255, 0.1)",
      },
    });

    const series = chart.addSeries(LineSeries, {
      color: color,
      lineWidth: 3,
      crosshairMarkerVisible: true,
      priceLineVisible: false,
    });

    const chartData = data.map((d) => ({
      time: d.date,
      value: d.value,
    }));
    
    series.setData(chartData);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartRef.current) chart.applyOptions({ width: chartRef.current.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, color, height]);

  return <div ref={chartRef} className="w-full" />;
}
