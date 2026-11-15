import type { Messages } from "@analysisace/i18n";

import { ApiError } from "./api";

export type ErrorCode = keyof Messages["errors"];

/** Result of a server action, kept by `useActionState`. */
export interface FormState {
  /** Translated by the form under `errors.<code>`. */
  error?: ErrorCode;
  ok?: boolean;
}

export const INITIAL_FORM_STATE: FormState = {};

const KNOWN_CODES: ReadonlySet<string> = new Set<ErrorCode>([
  "INVALID_CREDENTIALS",
  "ACCOUNT_LOCKED",
  "ACCOUNT_DISABLED",
  "EMAIL_TAKEN",
  "TERMS_REQUIRED",
  "INVALID_TOKEN",
  "WRONG_PASSWORD",
  "NOT_AUTHENTICATED",
  "FORBIDDEN",
  "LAST_ADMIN",
  "CANNOT_CHANGE_SELF",
  "USER_NOT_FOUND",
  "CONSENT_NOT_CHANGEABLE",
  "VALIDATION",
  "UNAVAILABLE",
]);

/** Maps a failed API call to a message code. Anything unexpected is logged and hidden. */
export function toFormError(error: unknown): FormState {
  if (error instanceof ApiError && KNOWN_CODES.has(error.code)) {
    return { error: error.code as ErrorCode };
  }
  console.error("Unexpected error in server action", error);
  return { error: "UNAVAILABLE" };
}

export function text(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

/** Passwords are not trimmed: leading or trailing spaces may be intended. */
export function secret(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value : "";
}
