/**
 * Server-side context for the personal finance pages (F12 to F26): the signed-in user,
 * the household they are looking at, and what their household role lets them do.
 */
import "server-only";

import type { Household, User } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { cookies } from "next/headers";

import { ApiError, request } from "./api";
import type { ErrorCode } from "./form-state";
import { getSessionToken, requireUser } from "./session";

export const HOUSEHOLD_COOKIE = "aa_household";

export interface PersonalContext {
  user: User;
  token: string;
  households: Household[];
  /** Null when the user has no household yet. */
  household: Household | null;
  /** Owners and editors may change records (FR24.2). */
  canEdit: boolean;
  isOwner: boolean;
}

export async function getPersonalContext(
  locale: Locale,
  returnTo: string,
): Promise<PersonalContext> {
  const user = await requireUser(locale, returnTo);
  const token = (await getSessionToken()) ?? "";
  const households = await request<Household[]>("/households", { token });
  const chosen = (await cookies()).get(HOUSEHOLD_COOKIE)?.value;
  const household = households.find((h) => h.id === chosen) ?? households[0] ?? null;
  return {
    user,
    token,
    households,
    household,
    canEdit: household?.role === "OWNER" || household?.role === "EDITOR",
    isOwner: household?.role === "OWNER",
  };
}

/** A GET under the current household, for example `hh(ctx, "/goals")`. */
export function hh<T>(ctx: PersonalContext, path: string): Promise<T> {
  if (!ctx.household) throw new ApiError(404, "HOUSEHOLD_NOT_FOUND", path);
  return request<T>(`/households/${ctx.household.id}${path}`, { token: ctx.token });
}

/** A GET that is not tied to a household, for example `/islamic-products`. */
export function get<T>(ctx: PersonalContext, path: string): Promise<T> {
  return request<T>(path, { token: ctx.token });
}

export type Loaded<T> = { ok: true; data: T } | { ok: false; code: ErrorCode };

/**
 * Loads one block of a page. A failure is shown in place of that block rather than
 * breaking the whole page.
 */
export async function load<T>(promise: Promise<T>): Promise<Loaded<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ok: false, code: error.code as ErrorCode };
    }
    console.error("Could not load personal finance data", error);
    return { ok: false, code: "UNAVAILABLE" };
  }
}
