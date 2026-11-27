import type { Messages } from "@analysisace/i18n";

import { ApiError } from "./api";

export type ErrorCode = keyof Messages["errors"];

/** Result of a server action, kept by `useActionState`. */
export interface FormState {
  /** Translated by the form under `errors.<code>`. */
  error?: ErrorCode;
  ok?: boolean;
  /** Counts from a CSV import, shown under the form. */
  imported?: { imported: number; updated: number; errors: { row?: number; error?: string }[] };
}

export const INITIAL_FORM_STATE: FormState = {};

const KNOWN_CODES: ReadonlySet<string> = new Set<ErrorCode>([
  "INVALID_CREDENTIALS",
  "ACCOUNT_LOCKED",
  "ACCOUNT_DISABLED",
  "EMAIL_TAKEN",
  "TERMS_REQUIRED",
  "INVALID_TOKEN",
  "VERIFY_TOKEN_INVALID",
  "PUSH_NOT_CONFIGURED",
  "PUSH_ENDPOINT_INVALID",
  "RATE_LIMITED",
  "EMAIL_UNCHANGED",
  "EMAIL_CHANGE_TOKEN_INVALID",
  "UNSUBSCRIBE_LINK_INVALID",
  "FIRM_ADMIN_REQUIRED",
  "SEAT_LIMIT_REACHED",
  "SEAT_LIMIT_BELOW_SEATS",
  "LAST_FIRM_ADMIN",
  "USER_NOT_FOUND",
  "LOGO_TOO_LARGE",
  "LOGO_INVALID",
  "NOTE_NOT_PUBLISHED",
  "WRONG_PASSWORD",
  "NOT_AUTHENTICATED",
  "FORBIDDEN",
  "LAST_ADMIN",
  "CANNOT_CHANGE_SELF",
  "USER_NOT_FOUND",
  "CONSENT_NOT_CHANGEABLE",
  "VALIDATION",
  "UNAVAILABLE",
  // Personal finance (F12 to F26).
  "ALREADY_MEMBER",
  "CATEGORY_EXISTS",
  "CATEGORY_IN_USE",
  "CATEGORY_NOT_FOUND",
  "CONSENT_REQUIRED",
  "CSV_HEADER_INVALID",
  "DOCUMENT_TOO_LARGE",
  "DOCUMENT_UNAVAILABLE",
  "ENCRYPTION_NOT_CONFIGURED",
  "EVENT_DATA_MISSING",
  "EVENT_NOT_FOUND",
  "HOUSEHOLD_NOT_FOUND",
  "HOUSEHOLD_ROLE_REQUIRED",
  "LAST_OWNER",
  "NISAB_BASIS_REQUIRED",
  "NISAB_PRICE_REQUIRED",
  "NOT_ENOUGH_BALANCE",
  "NOT_ENOUGH_UNITS",
  "NOT_FOUND",
  "OWNER_SHARES_INVALID",
  "PLAN_NEVER_REACHES_FIRE",
  "TAX_YEAR_INVALID",
  "TRANSACTION_NOT_REVERSIBLE",
  "UNITS_REQUIRED",
  "UNKNOWN_TICKER",
  "TARGETS_MUST_TOTAL_100",
  // Market layer (F1 to F8) and its admin screens.
  "NOT_SCREENED",
  "DUPLICATE",
  "PRICE_CHANGE_TOO_LARGE",
  "CSV_INVALID",
  "FIGURE_WITHOUT_SOURCE",
  "LIMIT_REACHED",
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

/** An optional text field: empty means "not given". */
export function optional(form: FormData, name: string): string | undefined {
  const value = text(form, name);
  return value === "" ? undefined : value;
}

/** A checkbox or switch: present and "on" when ticked. */
export function checked(form: FormData, name: string): boolean {
  return form.get(name) === "on";
}
