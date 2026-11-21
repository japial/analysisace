/**
 * Labels for market codes. Works with both server and client translators.
 */

// next-intl's translator types differ between server and client; both have `t(key)` and `t.has`.
interface Translate {
  (key: never, values?: never): string;
  has(key: never): boolean;
}

function label(t: Translate, key: string, fallback: string): string {
  return t.has(key as never) ? t(key as never) : fallback;
}

/** "EASING|HIGH|CALM" -> "Easing, inflation high, oil calm". */
export function regimeLabel(t: Translate, code: string | null | undefined): string {
  if (!code) return "—";
  const [rate = "UNKNOWN", inflation = "UNKNOWN", oil = "UNKNOWN"] = code.split("|");
  return [
    label(t, `market.regime.rate.${rate}`, rate),
    label(t, `market.regime.inflation.${inflation}`, inflation),
    label(t, `market.regime.oil.${oil}`, oil),
  ].join(", ");
}

export function statusLabel(t: Translate, status: string | null | undefined): string {
  if (!status) return "—";
  return label(t, `market.status.${status}`, status);
}

export function seriesLabel(t: Translate, code: string): string {
  return label(t, `market.series.${code}`, code);
}

export function eventTypeLabel(t: Translate, type: string): string {
  return label(t, `market.eventType.${type}`, type);
}

export function methodLabel(t: Translate, method: string): string {
  return label(t, `market.methodLabel.${method}`, method);
}

export function ruleLabel(t: Translate, rule: string): string {
  return label(t, `market.screen.rules.${rule}`, rule);
}
