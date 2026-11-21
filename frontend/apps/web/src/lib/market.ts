/**
 * Server-side loading for the market pages (F1 to F8) and their admin screens. Public reads
 * are cached like other market data; admin reads send the session token and are not cached.
 */
import "server-only";

import type { Permission } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ApiError, request } from "./api";
import { formatterFor } from "./fmt";
import type { ErrorCode } from "./form-state";
import { getCurrentUser, getSessionToken, requirePermission } from "./session";

export type Loaded<T> = { ok: true; data: T } | { ok: false; code: ErrorCode; status: number };

/** One block of a page. A failure shows in place of that block. */
export async function loadPublic<T>(path: string): Promise<Loaded<T>> {
  return settle(request<T>(path));
}

export async function settle<T>(promise: Promise<T>): Promise<Loaded<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ok: false, code: error.code as ErrorCode, status: error.status };
    }
    console.error("Could not load market data", error);
    return { ok: false, code: "UNAVAILABLE", status: 503 };
  }
}

/** Locale, messages and formatters for a public market page. */
export async function marketSetup(locale: string) {
  setRequestLocale(locale as Locale);
  const t = await getTranslations();
  return { t, f: formatterFor(locale), locale: locale as Locale };
}

/** For an admin page: the permission is checked here and again by the API. */
export async function adminSetup(locale: string, returnTo: string, permission: Permission) {
  setRequestLocale(locale as Locale);
  const user = await requirePermission(locale as Locale, returnTo, permission);
  const token = (await getSessionToken()) ?? "";
  const t = await getTranslations();
  const admin = <T>(path: string) => settle(request<T>(path, { token }));
  return { t, f: formatterFor(locale), locale: locale as Locale, user, token, admin };
}

/** The signed-in user's token, or null for a visitor. */
export async function optionalToken(): Promise<string | null> {
  const user = await getCurrentUser();
  return user ? await getSessionToken() : null;
}

/** "en" or "bn" text of a bilingual record. */
export function pick(row: object, field: string, locale: string): string {
  const value = (row as Record<string, unknown>)[`${field}_${locale === "bn" ? "bn" : "en"}`];
  return typeof value === "string" ? value : "";
}
