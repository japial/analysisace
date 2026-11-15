import type { DigitSystem } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";

/**
 * Digit style for a language. PRD section 12 makes digits a per-user setting; until user
 * accounts exist (M2), Bangla pages use Bangla digits and English pages use Latin digits.
 */
export function digitsFor(locale: Locale): DigitSystem {
  return locale === "bn" ? "bn" : "latn";
}
