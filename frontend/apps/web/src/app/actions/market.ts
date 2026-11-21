"use server";

/**
 * Server actions for the market layer: the watchlist (FR7.1) and the admin screens. The API
 * checks every permission; these only shape the form into the API's request.
 */
import { revalidatePath } from "next/cache";

import { request } from "@/lib/api";
import { type FormState, checked, optional, text, toFormError } from "@/lib/form-state";
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

const enc = encodeURIComponent;

/** Empty string becomes null so the API stores "not stated". */
function nullable(form: FormData, name: string): string | null {
  return optional(form, name) ?? null;
}

// --- watchlist ------------------------------------------------------------------------

export async function setWatchAction(ticker: string, watch: boolean): Promise<FormState> {
  return run(() => call(watch ? "PUT" : "DELETE", `/watchlist/${enc(ticker)}`));
}

// --- data -----------------------------------------------------------------------------

export async function setIssueStatusAction(issueId: string, status: string): Promise<FormState> {
  return run(() => call("PATCH", `/admin/data-issues/${enc(issueId)}`, { status }));
}

export async function runQualityChecksAction(): Promise<FormState> {
  return run(() => call("POST", "/admin/jobs/data-quality/run"));
}

export async function runAnalyticsAction(): Promise<FormState> {
  return run(() => call("POST", "/admin/jobs/market-analytics/run"));
}

export async function addMetalPriceAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("POST", "/admin/metal-prices", {
      code: text(form, "code"),
      date: text(form, "date"),
      value: text(form, "value"),
      note: nullable(form, "note"),
    }),
  );
}

export async function importSeriesAction(_: FormState, form: FormData): Promise<FormState> {
  const file = form.get("file");
  const content = file instanceof File && file.size > 0 ? await file.text() : text(form, "content");
  try {
    const result = await call<{ inserted: number; updated: number; errors: string[] }>(
      "POST",
      "/admin/series/import",
      {
        kind: text(form, "kind"),
        content,
        source_name: text(form, "source_name"),
        source_url: nullable(form, "source_url"),
      },
    );
    revalidatePath("/", "layout");
    return {
      ok: result.errors.length === 0,
      imported: {
        imported: result.inserted,
        updated: result.updated,
        errors: result.errors.map((error) => ({ error })),
      },
    };
  } catch (error) {
    return toFormError(error);
  }
}

export async function addCorporateActionAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("POST", "/admin/corporate-actions", {
      ticker: text(form, "ticker").toUpperCase(),
      ex_date: text(form, "ex_date"),
      type: text(form, "type"),
      ratio: nullable(form, "ratio"),
      amount: nullable(form, "amount"),
      source_name: text(form, "source_name"),
      source_url: nullable(form, "source_url"),
    }),
  );
}

// --- Shariah (F1) ---------------------------------------------------------------------

const FIGURES = [
  "total_debt_interest_bearing",
  "cash_and_interest_securities",
  "receivables",
  "total_revenue",
  "non_permissible_income",
  "zakatable_assets",
] as const;

export async function saveFinancialsAction(
  ticker: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const shares = optional(form, "shares_outstanding");
  const page = optional(form, "source_page");
  return run(() =>
    call("PUT", "/admin/financials", {
      ticker,
      period_end: text(form, "period_end"),
      period_type: text(form, "period_type"),
      ...Object.fromEntries(FIGURES.map((name) => [name, nullable(form, name)])),
      shares_outstanding: shares ? Number(shares) : null,
      source_name: text(form, "source_name"),
      source_url: nullable(form, "source_url"),
      source_page: page ? Number(page) : null,
    }),
  );
}

export async function reviewFinancialsAction(financialsId: string): Promise<FormState> {
  return run(() => call("POST", `/admin/financials/${enc(financialsId)}/review`));
}

export async function setClassificationAction(
  ticker: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const pass = checked(form, "stage1_pass");
  return run(() =>
    call("PUT", `/admin/shariah/${enc(ticker)}/classification`, {
      stage1_pass: pass,
      activity: pass ? null : nullable(form, "activity"),
      reason: text(form, "reason"),
    }),
  );
}

export async function setOverrideAction(
  ticker: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const status = text(form, "status");
  return run(() =>
    call("PUT", `/admin/shariah/${enc(ticker)}/override`, {
      status: status && status !== "NONE" ? status : null,
      reason: text(form, "reason"),
    }),
  );
}

export async function setBoardNoteAction(
  ticker: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() => call("PUT", `/admin/shariah/${enc(ticker)}/board-note`, { note: nullable(form, "note") }));
}

// --- events (FR5.1) -------------------------------------------------------------------

/** "Label | https://link" per line. */
function sourceLinks(form: FormData): { label: string; url: string }[] {
  return text(form, "source_links")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [label = "", url = ""] = line.includes("|") ? line.split("|") : [line, line];
      return { label: label.trim() || url.trim(), url: url.trim() };
    });
}

function eventBody(form: FormData) {
  return {
    type: text(form, "type"),
    t0: text(form, "t0"),
    title_en: text(form, "title_en"),
    title_bn: text(form, "title_bn"),
    description_en: text(form, "description_en"),
    description_bn: text(form, "description_bn"),
    source_links: sourceLinks(form),
  };
}

export async function createEventAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() => call("POST", "/admin/events", { slug: text(form, "slug"), ...eventBody(form) }));
}

export async function updateEventAction(eventId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() => call("PATCH", `/admin/events/${enc(eventId)}`, eventBody(form)));
}

export async function publishEventAction(eventId: string, published: boolean): Promise<FormState> {
  return run(() => call("POST", `/admin/events/${enc(eventId)}/publish`, { published }));
}

export async function deleteEventAction(eventId: string): Promise<FormState> {
  return run(() => call("DELETE", `/admin/events/${enc(eventId)}`));
}

// --- macro notes (FR4) ----------------------------------------------------------------

export async function generateNoteAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("POST", "/admin/notes/generate", {
      week_start: text(form, "week_start"),
      replace_draft: checked(form, "replace_draft"),
    }),
  );
}

export async function editNoteAction(noteId: string, _: FormState, form: FormData): Promise<FormState> {
  return run(() =>
    call("PATCH", `/admin/notes/${enc(noteId)}`, { title: text(form, "title"), body: text(form, "body") }),
  );
}

export async function publishNoteAction(noteId: string, published: boolean): Promise<FormState> {
  return run(() => call("POST", `/admin/notes/${enc(noteId)}/publish`, { published }));
}

// --- bank flags (FR26.5) --------------------------------------------------------------

export async function setBankFlagAction(_: FormState, form: FormData): Promise<FormState> {
  const links = sourceLinks(form).map((link) => ({ title: link.label, url: link.url }));
  return run(() =>
    call("PUT", "/admin/bank-flags", {
      bank: text(form, "bank"),
      status: text(form, "status"),
      note_en: text(form, "note_en"),
      note_bn: text(form, "note_bn"),
      source_links: links,
    }),
  );
}

export async function deleteBankFlagAction(flagId: string): Promise<FormState> {
  return run(() => call("DELETE", `/admin/bank-flags/${enc(flagId)}`));
}
