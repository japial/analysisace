/**
 * Number, money and date formatting for Bangladesh (PRD section 12).
 *
 * - Grouping is always South Asian: 12,34,567 (lakh and crore).
 * - Digits are Bangla or Latin, chosen separately from the UI language.
 * - Money arrives from the API as a decimal string and is formatted from that string,
 *   so no value passes through a binary float.
 * - Dates are shown in Asia/Dhaka.
 *
 * Shared by the web app and, later, the mobile app. Keep it free of React and Next.js.
 */

export type DigitSystem = "bn" | "latn";

/** A decimal number as the API sends it ("304.2000"), or a JS number for non-money values. */
export type Numeric = string | number;

export const DHAKA_TIME_ZONE = "Asia/Dhaka";

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

function numberFormat(digits: DigitSystem, options: Intl.NumberFormatOptions): Intl.NumberFormat {
  // en-IN gives lakh/crore grouping; the numbering system swaps the digit glyphs.
  return new Intl.NumberFormat("en-IN", {
    ...options,
    numberingSystem: digits === "bn" ? "beng" : "latn",
  });
}

function checked(value: Numeric): Intl.StringNumericLiteral | number {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new RangeError(`Not a finite number: ${value}`);
    return value;
  }
  if (!DECIMAL_PATTERN.test(value)) throw new RangeError(`Not a decimal string: "${value}"`);
  return value as Intl.StringNumericLiteral;
}

export interface NumberOptions {
  digits?: DigitSystem;
  minFractionDigits?: number;
  maxFractionDigits?: number;
}

export function formatNumber(value: Numeric, options: NumberOptions = {}): string {
  const { digits = "latn", minFractionDigits = 0, maxFractionDigits = 2 } = options;
  return numberFormat(digits, {
    minimumFractionDigits: minFractionDigits,
    maximumFractionDigits: Math.max(minFractionDigits, maxFractionDigits),
  }).format(checked(value));
}

/** Taka amount with two decimals: "৳12,34,567.50". */
export function formatBDT(value: Numeric, options: { digits?: DigitSystem } = {}): string {
  const amount = formatNumber(value, {
    digits: options.digits,
    minFractionDigits: 2,
    maxFractionDigits: 2,
  });
  return amount.startsWith("-") ? `-৳${amount.slice(1)}` : `৳${amount}`;
}

const LAKH = 100_000;
const CRORE = 10_000_000;

const UNIT_LABELS = {
  en: { lakh: "lakh", crore: "crore" },
  bn: { lakh: "লাখ", crore: "কোটি" },
} as const;

/**
 * Short taka amount for cards and charts: "৳12.35 lakh", "৳3.2 crore".
 * Rounded for display only; never use the result in a calculation.
 */
export function formatCompactBDT(
  value: Numeric,
  options: { digits?: DigitSystem; language?: "bn" | "en" } = {},
): string {
  const { digits = "latn", language = "en" } = options;
  const amount = Number(checked(value));
  const size = Math.abs(amount);
  if (size < LAKH) return formatBDT(value, { digits });
  const [divisor, unit] = size >= CRORE ? [CRORE, "crore" as const] : [LAKH, "lakh" as const];
  const scaled = formatNumber(size / divisor, { digits, maxFractionDigits: 2 });
  return `${amount < 0 ? "-" : ""}৳${scaled} ${UNIT_LABELS[language][unit]}`;
}

/** Percentage from a value already in percent: 4.42 -> "4.42%". */
export function formatPercent(
  value: Numeric,
  options: { digits?: DigitSystem; fractionDigits?: number; signed?: boolean } = {},
): string {
  const { digits = "latn", fractionDigits = 2, signed = false } = options;
  const text = formatNumber(value, {
    digits,
    minFractionDigits: fractionDigits,
    maxFractionDigits: fractionDigits,
  });
  const positive = Number(checked(value)) > 0;
  return `${signed && positive ? "+" : ""}${text}%`;
}

function parseDate(value: string | Date): Date {
  // A bare date ("2026-11-12") is a calendar day, not an instant. Pin it to noon UTC so
  // it shows as the same day in Dhaka (UTC+6).
  const date =
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? new Date(`${value}T12:00:00Z`)
      : new Date(value);
  if (Number.isNaN(date.getTime())) throw new RangeError(`Not a date: ${String(value)}`);
  return date;
}

export interface DateOptions {
  language?: "bn" | "en";
  digits?: DigitSystem;
  withTime?: boolean;
}

/** Date in Asia/Dhaka: "12 Nov 2026" or "১২ নভে, ২০২৬". With time: adds 24-hour "17:30". */
export function formatDate(value: string | Date, options: DateOptions = {}): string {
  const { language = "en", digits = "latn", withTime = false } = options;
  return new Intl.DateTimeFormat(language === "bn" ? "bn-BD" : "en-GB", {
    timeZone: DHAKA_TIME_ZONE,
    numberingSystem: digits === "bn" ? "beng" : "latn",
    day: "numeric",
    month: "short",
    year: "numeric",
    // 24-hour time: the Bangla locale data prints "AM/PM" in Latin letters otherwise.
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" } : {}),
  }).format(parseDate(value));
}
