"use server";

/**
 * Server actions for firm accounts (F9, D30). The API checks every seat and permission and
 * answers 404 while firm features are switched off; these only shape the forms.
 */
import type { FirmApiKeyCreated } from "@analysisace/core";
import { revalidatePath } from "next/cache";

import { request } from "@/lib/api";
import { type FormState, optional, text, toFormError } from "@/lib/form-state";
import { requireToken } from "@/lib/session";

type Method = "POST" | "PUT" | "PATCH" | "DELETE";

async function call<T = unknown>(method: Method, path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method, body, token: await requireToken() });
}

async function run(fn: () => Promise<unknown>): Promise<FormState> {
  try {
    await fn();
  } catch (error) {
    return toFormError(error);
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

const firm = (id: string, path = "") => `/firms/${id}${path}`;

// --- members (FR9.3) -------------------------------------------------------------------

export async function addFirmMemberAction(firmId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("POST", firm(firmId, "/members"), { email: text(form, "email"), role: text(form, "role") || "MEMBER" }),
  );
}

export async function setFirmRoleAction(firmId: string, userId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() => call("PATCH", firm(firmId, `/members/${userId}`), { role: text(form, "role") }));
}

export async function removeFirmMemberAction(firmId: string, userId: string): Promise<FormState> {
  return run(() => call("DELETE", firm(firmId, `/members/${userId}`)));
}

// --- report settings (FR9.1) -------------------------------------------------------------

export async function setFirmDisclaimerAction(firmId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() => call("PATCH", firm(firmId), { report_disclaimer: optional(form, "report_disclaimer") ?? "" }));
}

export async function setFirmLogoAction(firmId: string, _: FormState, form: FormData): Promise<FormState> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "VALIDATION" };
  const content = Buffer.from(await file.arrayBuffer()).toString("base64");
  return run(() => call("PUT", firm(firmId, "/logo"), { content_base64: content }));
}

export async function removeFirmLogoAction(firmId: string): Promise<FormState> {
  return run(() => call("DELETE", firm(firmId, "/logo")));
}

// --- API keys (FR9.2) ---------------------------------------------------------------------

export interface KeyFormState extends FormState {
  /** The new key, shown once. */
  key?: string;
}

export async function createApiKeyAction(firmId: string, _: KeyFormState, form: FormData): Promise<KeyFormState> {
  try {
    const created = await call<FirmApiKeyCreated>("POST", firm(firmId, "/api-keys"), { name: text(form, "name") });
    revalidatePath("/", "layout");
    return { ok: true, key: created.key };
  } catch (error) {
    return toFormError(error);
  }
}

export async function revokeApiKeyAction(firmId: string, keyId: string): Promise<FormState> {
  return run(() => call("DELETE", firm(firmId, `/api-keys/${keyId}`)));
}

// --- platform administration ------------------------------------------------------------

export async function createFirmAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("POST", "/admin/firms", {
      name: text(form, "name"),
      seat_limit: Number(text(form, "seat_limit") || "5"),
      admin_email: text(form, "admin_email"),
      report_disclaimer: optional(form, "report_disclaimer"),
    }),
  );
}

export async function setFirmSeatLimitAction(firmId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() => call("PATCH", `/admin/firms/${firmId}`, { seat_limit: Number(text(form, "seat_limit")) }));
}

export async function setFirmActiveAction(firmId: string, active: boolean): Promise<FormState> {
  return run(() => call("PATCH", `/admin/firms/${firmId}`, { is_active: active }));
}

