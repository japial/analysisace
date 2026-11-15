/**
 * The web session. The API issues an opaque token at sign-in; this server keeps it in an
 * httpOnly cookie and sends it to the API as a Bearer header. Browser scripts can never
 * read it (docs/DECISIONS.md, D10).
 */
import "server-only";

import type { Permission, User } from "@analysisace/core";
import type { Locale } from "@analysisace/i18n";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { cache } from "react";

import { redirect } from "@/i18n/navigation";

import { ApiError, getMe } from "./api";

const SESSION_COOKIE = "dn_session";

export async function getSessionToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

/** Only callable from a server action or route handler. */
export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(expiresAt),
  });
}

/** Only callable from a server action or route handler. */
export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}

/** The signed-in user, or null. Fetched once per request however often it is called. */
export const getCurrentUser = cache(async (): Promise<User | null> => {
  const token = await getSessionToken();
  if (!token) return null;
  try {
    return await getMe(token);
  } catch (error) {
    // An expired or revoked session is the same as being signed out.
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
});

/** Sends visitors who are not signed in to the sign-in page, then back to `returnTo`. */
export async function requireUser(locale: Locale, returnTo: string): Promise<User> {
  const user = await getCurrentUser();
  if (!user) {
    return redirect({ href: { pathname: "/signin", query: { next: returnTo } }, locale });
  }
  return user;
}

/**
 * Requires a permission. A signed-in user without it gets the not-found page, so the
 * existence of admin pages is not revealed.
 */
export async function requirePermission(
  locale: Locale,
  returnTo: string,
  permission: Permission,
): Promise<User> {
  const user = await requireUser(locale, returnTo);
  if (!user.permissions.includes(permission)) notFound();
  return user;
}

/** The token for an API call from a server action. Throws the same error the API would. */
export async function requireToken(): Promise<string> {
  const token = await getSessionToken();
  if (!token) throw new ApiError(401, "NOT_AUTHENTICATED", "session");
  return token;
}

/**
 * Accepts only a path inside this site, so a crafted `next` value cannot send someone to
 * another site after sign-in.
 */
export function safeReturnPath(value: FormDataEntryValue | string | null | undefined): string {
  if (typeof value !== "string") return "/";
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "/";
  return value;
}
