import type { SeriesPoint } from "@analysisace/core";

import type { ChartPoint } from "@/components/personal/line-chart";

/** Most points a line chart draws; longer series show every n-th point (the table keeps the shape). */
const MAX_POINTS = 320;

/**
 * Joins several API series on their dates for `LineChart`. Values stay decimal strings.
 * Long series are thinned to every n-th date, always keeping the last one.
 */
export function joinSeries(
  series: Record<string, SeriesPoint[]>,
  label: (date: string) => string,
): ChartPoint[] {
  const byDate = new Map<string, Record<string, string | null>>();
  for (const [key, points] of Object.entries(series)) {
    for (const point of points) {
      const row = byDate.get(point.date) ?? {};
      row[key] = point.value;
      byDate.set(point.date, row);
    }
  }
  const dates = [...byDate.keys()].sort();
  const step = Math.max(1, Math.ceil(dates.length / MAX_POINTS));
  const kept = dates.filter((_, i) => i % step === 0 || i === dates.length - 1);
  return kept.map((date) => {
    const values = byDate.get(date) ?? {};
    const filled: Record<string, string | null> = {};
    for (const key of Object.keys(series)) filled[key] = values[key] ?? null;
    return { label: label(date), values: filled };
  });
}
