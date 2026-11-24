/** Shared start of every personal finance page. */
import "server-only";

import type { Member } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { formatterFor } from "./fmt";
import { getPersonalContext } from "./personal";

export interface PageProps<P extends object = object> {
  params: Promise<{ locale: string } & P>;
}

export type Section =
  | "overview"
  | "income"
  | "setup"
  | "costs"
  | "portfolio"
  | "assets"
  | "sukuk"
  | "performance"
  | "allocation"
  | "marketCheck"
  | "zakat"
  | "tax"
  | "fire"
  | "goals"
  | "alerts"
  | "community"
  | "household";

export function sectionMetadata(section: Section) {
  return async ({ params }: PageProps): Promise<Metadata> => {
    const { locale } = await params;
    const t = await getTranslations({ locale: locale as Locale, namespace: "personal.sections" });
    return { title: t(section) };
  };
}

/** Locale, signed-in context (redirects to sign-in), messages and formatters. */
export async function setup(locale: string, returnTo: string) {
  setRequestLocale(locale as Locale);
  const ctx = await getPersonalContext(locale as Locale, returnTo);
  const t = await getTranslations();
  return { ctx, t, f: formatterFor(locale), locale: locale as Locale };
}

type Translator = Awaited<ReturnType<typeof getTranslations>>;

/** Label for an API value, falling back to the value itself for one the UI does not know. */
export function enumLabel(t: Translator, group: string, value: string | null | undefined): string {
  if (!value) return "—";
  const key = `personal.enum.${group}.${value}`;
  return t.has(key as never) ? t(key as never) : value;
}

/** Options for an API value list, labelled from `personal.enum.<group>`. */
export function enumOptions(t: Translator, group: string, values: readonly string[]) {
  return values.map((value) => ({ value, label: enumLabel(t, group, value) }));
}

export function memberOptions(members: Member[]) {
  return members.map((m) => ({ value: m.id, label: m.display_name }));
}

/** Today in Dhaka as "YYYY-MM-DD", the default for date fields. */
export function todayDhaka(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(new Date());
}
