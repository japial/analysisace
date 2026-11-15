"use server";

import type { OptionalConsent } from "@analysisace/core";
import { isLocale } from "@analysisace/i18n";
import { revalidatePath } from "next/cache";
import { getLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";
import * as api from "@/lib/api";
import { type FormState, secret, text, toFormError } from "@/lib/form-state";
import { clearSessionCookie, requireToken } from "@/lib/session";

const OPTIONAL_CONSENTS: OptionalConsent[] = [
  "MARKETING",
  "RELIGIOUS_PREFERENCES",
  "COMMUNITY_BENCHMARKING",
];

export async function updateProfileAction(_: FormState, form: FormData): Promise<FormState> {
  const chosen = text(form, "locale");
  const current = await getLocale();
  try {
    await api.updateMe(await requireToken(), {
      full_name: text(form, "full_name"),
      locale: isLocale(chosen) ? chosen : undefined,
    });
  } catch (error) {
    return toFormError(error);
  }
  if (isLocale(chosen) && chosen !== current) {
    // Show the account page in the newly preferred language.
    return redirect({ href: "/account", locale: chosen });
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

export async function changePasswordAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.changePassword(await requireToken(), {
      current_password: secret(form, "current_password"),
      new_password: secret(form, "new_password"),
    });
  } catch (error) {
    return toFormError(error);
  }
  return { ok: true };
}

export async function updateConsentsAction(_: FormState, form: FormData): Promise<FormState> {
  const consents = Object.fromEntries(
    OPTIONAL_CONSENTS.map((purpose) => [purpose, form.get(purpose) === "on"]),
  );
  try {
    await api.updateConsents(await requireToken(), consents);
  } catch (error) {
    return toFormError(error);
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

export async function deleteAccountAction(_: FormState, form: FormData): Promise<FormState> {
  try {
    await api.deleteMe(await requireToken(), secret(form, "password"));
  } catch (error) {
    return toFormError(error);
  }
  await clearSessionCookie();
  return redirect({ href: "/", locale: await getLocale() });
}
