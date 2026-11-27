"use server";

import type { AuthResult } from "@analysisace/core";
import { revalidatePath } from "next/cache";
import { headers } from "next/headers";
import { getLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";
import * as api from "@/lib/api";
import { type FormState, secret, text, toFormError } from "@/lib/form-state";
import {
  clearSessionCookie,
  getSessionToken,
  safeReturnPath,
  setSessionCookie,
} from "@/lib/session";

async function browserUserAgent(): Promise<string | null> {
  return (await headers()).get("user-agent");
}

/**
 * The visitor's address as this server received it (D28): the first X-Forwarded-For entry
 * set by the proxy in front of the web app, else X-Real-IP. The API believes it only
 * because it comes from this server.
 */
async function visitorAddress(): Promise<string | null> {
  const incoming = await headers();
  const forwarded = incoming.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || incoming.get("x-real-ip")?.trim() || null;
}

export async function signInAction(_: FormState, form: FormData): Promise<FormState> {
  let result: AuthResult;
  try {
    result = await api.login(
      { email: text(form, "email"), password: secret(form, "password") },
      await browserUserAgent(),
      await visitorAddress(),
    );
  } catch (error) {
    return toFormError(error);
  }
  await setSessionCookie(result.token, result.expires_at);
  return redirect({ href: safeReturnPath(form.get("next")), locale: await getLocale() });
}

export async function signUpAction(_: FormState, form: FormData): Promise<FormState> {
  const locale = await getLocale();
  let result: AuthResult;
  try {
    result = await api.register(
      {
        email: text(form, "email"),
        password: secret(form, "password"),
        full_name: text(form, "full_name"),
        locale,
        accept_terms: form.get("accept_terms") === "on",
      },
      await browserUserAgent(),
      await visitorAddress(),
    );
  } catch (error) {
    return toFormError(error);
  }
  await setSessionCookie(result.token, result.expires_at);
  // D38: a new account starts in My money, where the household is set up, unless the
  // person was on their way somewhere else.
  const next = safeReturnPath(form.get("next"));
  return redirect({ href: next === "/" ? "/personal" : next, locale });
}

export async function signOutAction(): Promise<void> {
  const token = await getSessionToken();
  if (token) {
    // The cookie is cleared even if the API cannot be reached.
    await api.logout(token).catch(() => undefined);
  }
  await clearSessionCookie();
  redirect({ href: "/", locale: await getLocale() });
}

export async function requestPasswordResetAction(
  _: FormState,
  form: FormData,
): Promise<FormState> {
  try {
    await api.requestPasswordReset(text(form, "email"), await visitorAddress());
  } catch (error) {
    return toFormError(error);
  }
  // The same answer whether or not the email has an account.
  return { ok: true };
}

export async function confirmPasswordResetAction(
  _: FormState,
  form: FormData,
): Promise<FormState> {
  try {
    await api.confirmPasswordReset(text(form, "token"), secret(form, "new_password"));
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}

/** D25: send a new confirmation link to the signed-in person. */
export async function resendVerificationAction(): Promise<FormState> {
  const token = await getSessionToken();
  if (!token) return { error: "NOT_AUTHENTICATED" };
  try {
    await api.requestEmailVerification(token);
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}

/** D39: the button on the page the link sent to a new address opens. */
export async function confirmEmailChangeAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.confirmEmailChange(text(form, "token"));
  } catch (error) {
    return toFormError(error);
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

/** D34: the confirm button on the unsubscribe page. */
export async function unsubscribeAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.unsubscribeByLink(text(form, "token"));
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}

/** D25: the button on the page the emailed link opens. */
export async function confirmEmailAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.confirmEmailVerification(text(form, "token"));
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}
