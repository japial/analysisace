"use client";

/**
 * A small line chart: one shared y-axis, 2 px lines, a crosshair with a tooltip on hover
 * or touch, a legend, and the same numbers as a table for anyone who cannot use the chart.
 *
 * Values arrive as API decimal strings. They are turned into numbers only to place points
 * on the screen; every number shown as text is formatted from the original string.
 */
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { formatterFor } from "@/lib/fmt";

export interface ChartSeries {
  key: string;
  label: string;
}

export interface ChartPoint {
  /** Already formatted for display, for example a date or an age. */
  label: string;
  values: Record<string, string | null>;
}

interface Props {
  title: string;
  series: ChartSeries[];
  points: ChartPoint[];
  /** How y values are shown: taka (lakh/crore) or a plain index number. */
  kind: "bdt" | "index";
  /** A horizontal reference line, for example the FIRE number. */
  reference?: { value: string; label: string };
}

const COLORS = ["var(--viz-1)", "var(--viz-2)", "var(--viz-3)", "var(--viz-4)"];
const HEIGHT = 260;
const PAD = { top: 12, right: 12, bottom: 28, left: 72 };

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const span = max - min;
  const step = 10 ** Math.floor(Math.log10(span / count));
  const unit = [1, 2, 2.5, 5, 10].map((m) => m * step).find((s) => span / s <= count) ?? span;
  const start = Math.floor(min / unit) * unit;
  const ticks: number[] = [];
  for (let v = start; v <= max + unit / 2; v += unit) ticks.push(Number(v.toPrecision(12)));
  return ticks;
}

export function LineChart({ title, series, points, kind, reference }: Props) {
  const t = useTranslations("personal.chart");
  const locale = useLocale();
  const f = formatterFor(locale);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.max(280, Math.round(entry.contentRect.width)));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const show = (value: string | null | undefined) =>
    kind === "bdt" ? f.compact(value) : f.num(value, 1);

  const geometry = useMemo(() => {
    const numbers = points.flatMap((p) =>
      series.map((s) => p.values[s.key]).filter((v): v is string => v != null).map(Number),
    );
    if (reference) numbers.push(Number(reference.value));
    const min = Math.min(...numbers, kind === "bdt" ? 0 : Infinity);
    const max = Math.max(...numbers);
    const ticks = niceTicks(min, max);
    const low = Math.min(min, ticks[0] ?? min);
    const high = Math.max(max, ticks[ticks.length - 1] ?? max);
    const innerW = width - PAD.left - PAD.right;
    const innerH = HEIGHT - PAD.top - PAD.bottom;
    const x = (i: number) => PAD.left + (points.length <= 1 ? 0 : (i / (points.length - 1)) * innerW);
    const y = (v: number) =>
      PAD.top + (high === low ? innerH / 2 : innerH - ((v - low) / (high - low)) * innerH);
    const paths = series.map((s) => {
      let d = "";
      let open = false;
      points.forEach((p, i) => {
        const raw = p.values[s.key];
        if (raw == null) {
          open = false;
          return;
        }
        d += `${open ? "L" : "M"}${x(i).toFixed(1)},${y(Number(raw)).toFixed(1)}`;
        open = true;
      });
      return d;
    });
    return { ticks, x, y, paths, innerW };
  }, [points, series, reference, width, kind]);

  if (points.length < 2) return null;

  const onMove = (clientX: number) => {
    const rect = box.current?.getBoundingClientRect();
    if (!rect) return;
    const ratio = (clientX - rect.left - PAD.left) / geometry.innerW;
    setHover(Math.max(0, Math.min(points.length - 1, Math.round(ratio * (points.length - 1)))));
  };

  const active = hover === null ? null : points[hover];
  const xLabels = [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="sr-only">{title}</figcaption>
      {series.length > 1 && (
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-secondary-foreground">
          {series.map((s, i) => (
            <li key={s.key} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-0.5 w-4 rounded"
                style={{ background: COLORS[i % COLORS.length] }}
              />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <div
        ref={box}
        className="relative w-full touch-pan-y select-none overflow-hidden"
        onPointerMove={(e) => onMove(e.clientX)}
        onPointerDown={(e) => onMove(e.clientX)}
        onPointerLeave={() => setHover(null)}
      >
        <svg width={width} height={HEIGHT} role="img" aria-label={title} className="block">
          {geometry.ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={width - PAD.right}
                y1={geometry.y(tick)}
                y2={geometry.y(tick)}
                stroke="var(--border)"
                strokeWidth={1}
              />
              <text
                x={PAD.left - 8}
                y={geometry.y(tick)}
                dy="0.32em"
                textAnchor="end"
                className="fill-muted-foreground text-[11px]"
              >
                {show(String(tick))}
              </text>
            </g>
          ))}
          {xLabels.map((index, n) => (
            <text
              key={`${index}-${n}`}
              x={geometry.x(index)}
              y={HEIGHT - 8}
              textAnchor={n === 0 ? "start" : n === 2 ? "end" : "middle"}
              className="fill-muted-foreground text-[11px]"
            >
              {points[index]?.label}
            </text>
          ))}
          {reference && (
            <g>
              <line
                x1={PAD.left}
                x2={width - PAD.right}
                y1={geometry.y(Number(reference.value))}
                y2={geometry.y(Number(reference.value))}
                stroke="var(--muted-foreground)"
                strokeDasharray="4 4"
                strokeWidth={1}
              />
              <text
                x={width - PAD.right}
                y={geometry.y(Number(reference.value)) - 6}
                textAnchor="end"
                className="fill-muted-foreground text-[11px]"
              >
                {reference.label}
              </text>
            </g>
          )}
          {geometry.paths.map((d, i) => (
            <path
              key={series[i]?.key}
              d={d}
              fill="none"
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}
          {hover !== null && active && (
            <g>
              <line
                x1={geometry.x(hover)}
                x2={geometry.x(hover)}
                y1={PAD.top}
                y2={HEIGHT - PAD.bottom}
                stroke="var(--muted-foreground)"
                strokeWidth={1}
              />
              {series.map((s, i) => {
                const raw = active.values[s.key];
                if (raw == null) return null;
                return (
                  <circle
                    key={s.key}
                    cx={geometry.x(hover)}
                    cy={geometry.y(Number(raw))}
                    r={4}
                    fill={COLORS[i % COLORS.length]}
                    stroke="var(--card)"
                    strokeWidth={2}
                  />
                );
              })}
            </g>
          )}
        </svg>
        {hover !== null && active && (
          <div
            role="status"
            className="pointer-events-none absolute top-2 z-10 min-w-36 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-sm"
            style={
              geometry.x(hover) > width / 2
                ? { right: width - geometry.x(hover) + 12 }
                : { left: geometry.x(hover) + 12 }
            }
          >
            <p className="mb-1 font-medium text-mono">{active.label}</p>
            {series.map((s, i) => (
              <p key={s.key} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5 text-secondary-foreground">
                  <span
                    aria-hidden="true"
                    className="inline-block size-2 rounded-full"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  {s.label}
                </span>
                <span className="text-mono tabular-nums">{show(active.values[s.key])}</span>
              </p>
            ))}
          </div>
        )}
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-secondary-foreground hover:text-mono">
          {t("showTable")}
        </summary>
        <div className="mt-2 max-h-72 overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-start text-muted-foreground">
                <th className="py-1 pe-3 text-start font-medium">{t("point")}</th>
                {series.map((s) => (
                  <th key={s.key} className="py-1 pe-3 text-end font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {points.map((p, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-1 pe-3">{p.label}</td>
                  {series.map((s) => (
                    <td key={s.key} className="py-1 pe-3 text-end tabular-nums">
                      {kind === "bdt" ? f.bdt(p.values[s.key]) : f.num(p.values[s.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
