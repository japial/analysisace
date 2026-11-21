/**
 * Locales and message files shared by the web app and, later, the mobile app.
 * English is the reference: its keys define the `Messages` type, and a test checks that
 * Bangla has exactly the same keys.
 */
import type en from "../messages/en.json";

export const locales = ["bn", "en"] as const;
export type Locale = (typeof locales)[number];

/** Bangla first: the product is built for Bangladesh (PRD section 3). */
export const defaultLocale: Locale = "bn";

export type Messages = typeof en;

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

export async function loadMessages(locale: Locale): Promise<Messages> {
  const loaded =
    locale === "bn" ? await import("../messages/bn.json") : await import("../messages/en.json");
  return loaded.default;
}
