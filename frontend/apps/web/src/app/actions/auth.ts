"use server";

import type { AuthResult } from "@analysisace/core";
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

export async function signInAction(_: FormState, form: FormData): Promise<FormState> {
  let result: AuthResult;
  try {
    result = await api.login(
      { email: text(form, "email"), password: secret(form, "password") },
      await browserUserAgent(),
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
    );
  } catch (error) {
    return toFormError(error);
  }
  await setSessionCookie(result.token, result.expires_at);
  return redirect({ href: safeReturnPath(form.get("next")), locale });
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
    await api.requestPasswordReset(text(form, "email"));
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

/** D25: the button on the page the emailed link opens. */
export async function confirmEmailAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.confirmEmailVerification(text(form, "token"));
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}
