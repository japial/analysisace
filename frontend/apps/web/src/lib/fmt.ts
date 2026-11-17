/**
 * Formatters bound to the page language, so pages call `f.bdt(x)` instead of passing the
 * digit system each time. Formatting only: every figure comes from the API.
 */
import {
  type Numeric,
  formatBDT,
  formatCompactBDT,
  formatDate,
  formatMonth,
  formatNumber,
  formatPercent,
} from "@analysisace/core";

import { digitsFor } from "./locale";

export type Formatter = ReturnType<typeof formatterFor>;

export function formatterFor(locale: string) {
  const language = locale === "bn" ? "bn" : "en";
  const digits = digitsFor(language);
  const orDash = <T>(value: T | null | undefined, fn: (v: T) => string) =>
    value === null || value === undefined || value === "" ? "—" : fn(value);
  return {
    language,
    digits,
    bdt: (value: Numeric | null | undefined) => orDash(value, (v) => formatBDT(v, { digits })),
    compact: (value: Numeric | null | undefined) =>
      orDash(value, (v) => formatCompactBDT(v, { digits, language })),
    pct: (value: Numeric | null | undefined, fractionDigits = 2, signed = false) =>
      orDash(value, (v) => formatPercent(v, { digits, fractionDigits, signed })),
    num: (value: Numeric | null | undefined, maxFractionDigits = 2) =>
      orDash(value, (v) => formatNumber(v, { digits, maxFractionDigits })),
    date: (value: string | null | undefined, withTime = false) =>
      orDash(value, (v) => formatDate(v, { language, digits, withTime })),
    /** "2026-11-01" -> "Nov 2026". */
    month: (value: string) => formatMonth(value, { language, digits }),
  };
}
