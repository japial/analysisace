"use server";

/**
 * Server actions for the personal finance pages (F12 to F26). Each one forwards a form to
 * the API; the API checks the household role and does every calculation. Numbers stay
 * decimal strings from the form to the API.
 */
import type { ImportResult } from "@analysisace/core";
import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { getLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";
import { request } from "@/lib/api";
import { type FormState, checked, optional, text, toFormError } from "@/lib/form-state";
import { HOUSEHOLD_COOKIE } from "@/lib/personal";
import { requireToken } from "@/lib/session";

type Method = "POST" | "PUT" | "PATCH" | "DELETE";

async function call<T = unknown>(method: Method, path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method, body, token: await requireToken() });
}

/** Runs one API call and refreshes the pages that show its data. */
async function run(fn: () => Promise<unknown>): Promise<FormState> {
  try {
    await fn();
  } catch (error) {
    return toFormError(error);
  }
  revalidatePath("/", "layout");
  return { ok: true };
}

async function go(href: string): Promise<never> {
  return redirect({ href, locale: await getLocale() });
}

const hh = (householdId: string, path = "") => `/households/${householdId}${path}`;

/** Owner split from the owners editor: parallel lists of member, outside name and percent. */
function owners(form: FormData) {
  const members = form.getAll("owner_member").map(String);
  const names = form.getAll("owner_external").map(String);
  const pcts = form.getAll("owner_pct").map(String);
  if (pcts.length === 0) return undefined;
  return pcts
    .map((pct, i) => ({
      pct: pct.trim(),
      member_id: members[i] && members[i] !== "EXTERNAL" ? members[i] : null,
      external_name: members[i] === "EXTERNAL" ? (names[i]?.trim() ?? null) : null,
    }))
    .filter((row) => row.pct !== "");
}

/** CSV from a chosen file, or else from the text box. */
async function csvFrom(form: FormData): Promise<string> {
  const file = form.get("file");
  if (file instanceof File && file.size > 0) return file.text();
  return text(form, "csv");
}

// --- F24 households and members --------------------------------------------------------

export async function createHouseholdAction(_: FormState, form: FormData): Promise<FormState> {
  return run(() => call("POST", "/households", { name: text(form, "name") }));
}

export async function renameHouseholdAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() => call("PATCH", hh(householdId), { name: text(form, "name") }));
}

export async function switchHouseholdAction(householdId: string): Promise<FormState> {
  (await cookies()).set(HOUSEHOLD_COOKIE, householdId, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
  });
  revalidatePath("/", "layout");
  return { ok: true };
}

export async function addMemberAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/members"), {
      display_name: text(form, "display_name"),
      role: text(form, "role") || "VIEWER",
      birth_year: optional(form, "birth_year"),
      email: optional(form, "email"),
    }),
  );
}

export async function updateMemberAction(
  householdId: string,
  memberId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const body: Record<string, unknown> = {
    display_name: optional(form, "display_name"),
    birth_year: optional(form, "birth_year"),
    hawl_date: optional(form, "hawl_date"),
    nisab_basis: optional(form, "nisab_basis"),
  };
  const role = optional(form, "role");
  if (role) body.role = role;
  return run(() => call("PATCH", hh(householdId, `/members/${memberId}`), body));
}

export async function removeMemberAction(householdId: string, memberId: string) {
  return run(() => call("DELETE", hh(householdId, `/members/${memberId}`)));
}

export async function setOwnersAction(
  householdId: string,
  kind: "HOLDING" | "ALT_ASSET" | "LIABILITY",
  assetId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("PUT", hh(householdId, `/owners/${kind}/${assetId}`), { owners: owners(form) ?? [] }),
  );
}

// --- F12 costs -------------------------------------------------------------------------

export async function addExpenseAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/expenses"), {
      date: text(form, "date"),
      amount: text(form, "amount"),
      category_id: text(form, "category_id"),
      note: optional(form, "note"),
      member_id: optional(form, "member_id"),
    }),
  );
}

export async function deleteExpenseAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/expenses/${id}`)));
}

export async function addRecurringAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/recurring"), {
      category_id: text(form, "category_id"),
      amount: text(form, "amount"),
      frequency: text(form, "frequency"),
      start_date: text(form, "start_date"),
      end_date: optional(form, "end_date"),
      note: optional(form, "note"),
      member_id: optional(form, "member_id"),
    }),
  );
}

export async function setRecurringActiveAction(householdId: string, id: string, active: boolean) {
  return run(() => call("PATCH", hh(householdId, `/recurring/${id}`), { is_active: active }));
}

export async function deleteRecurringAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/recurring/${id}`)));
}

export async function addCategoryAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() => call("POST", hh(householdId, "/categories"), { name: text(form, "name") }));
}

export async function deleteCategoryAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/categories/${id}`)));
}

export async function importExpensesAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  try {
    const result = await call<ImportResult>("POST", hh(householdId, "/imports/expenses"), {
      csv: await csvFrom(form),
    });
    revalidatePath("/", "layout");
    return { ok: true, imported: result };
  } catch (error) {
    return toFormError(error);
  }
}

// --- F14 accounts, holdings, liabilities ----------------------------------------------

export async function addAccountAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/accounts"), {
      type: text(form, "type"),
      institution: text(form, "institution"),
      name: text(form, "name"),
      number: optional(form, "number"),
    }),
  );
}

export async function deleteAccountAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/accounts/${id}`)));
}

export async function addHoldingAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/holdings"), {
      account_id: text(form, "account_id"),
      instrument_type: text(form, "instrument_type"),
      name: text(form, "name"),
      ticker: optional(form, "ticker")?.toUpperCase(),
      quantity: optional(form, "quantity"),
      cost: text(form, "cost"),
      manual_value: optional(form, "manual_value"),
      start_date: optional(form, "start_date"),
      maturity_date: optional(form, "maturity_date"),
      expected_rate: optional(form, "expected_rate"),
      payment_frequency: optional(form, "payment_frequency"),
      is_interest_bearing: checked(form, "is_interest_bearing"),
      owners: owners(form),
    }),
  );
}

export async function updateHoldingAction(
  householdId: string,
  id: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const fields = [
    "name",
    "quantity",
    "cost",
    "manual_value",
    "start_date",
    "maturity_date",
    "expected_rate",
    "final_rate",
    "payment_frequency",
    "profit_received",
    "tax_deducted",
  ];
  const body: Record<string, unknown> = Object.fromEntries(
    fields.map((name) => [name, optional(form, name)]).filter(([, value]) => value !== undefined),
  );
  body.is_interest_bearing = checked(form, "is_interest_bearing");
  return run(() => call("PATCH", hh(householdId, `/holdings/${id}`), body));
}

export async function deleteHoldingAction(householdId: string, id: string) {
  const result = await run(() => call("DELETE", hh(householdId, `/holdings/${id}`)));
  if (result.error) return result;
  return go("/personal/portfolio");
}

export async function addTransactionAction(
  householdId: string,
  holdingId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, `/holdings/${holdingId}/transactions`), {
      type: text(form, "type"),
      date: text(form, "date"),
      amount: text(form, "amount"),
      units: optional(form, "units"),
      note: optional(form, "note"),
    }),
  );
}

export async function deleteTransactionAction(householdId: string, holdingId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/holdings/${holdingId}/transactions/${id}`)));
}

export async function importBrokerAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  try {
    const result = await call<ImportResult>(
      "POST",
      hh(householdId, "/imports/broker-statement"),
      { account_id: text(form, "account_id"), csv: await csvFrom(form) },
    );
    revalidatePath("/", "layout");
    return { ok: true, imported: result };
  } catch (error) {
    return toFormError(error);
  }
}

export async function addLiabilityAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/liabilities"), {
      type: text(form, "type"),
      name: text(form, "name"),
      lender: optional(form, "lender"),
      outstanding: text(form, "outstanding"),
      due_within_year: optional(form, "due_within_year"),
      is_interest_bearing: checked(form, "is_interest_bearing"),
      end_date: optional(form, "end_date"),
      owners: owners(form),
    }),
  );
}

export async function updateLiabilityAction(
  householdId: string,
  id: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("PATCH", hh(householdId, `/liabilities/${id}`), {
      outstanding: optional(form, "outstanding"),
      due_within_year: optional(form, "due_within_year"),
    }),
  );
}

export async function deleteLiabilityAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/liabilities/${id}`)));
}

export async function recordNetWorthAction(householdId: string) {
  return run(() => call("POST", hh(householdId, "/portfolio/history")));
}

// --- F16 target allocation ------------------------------------------------------------

export async function setTargetsAction(
  householdId: string,
  assetClasses: string[],
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const targets = assetClasses
    .map((assetClass) => ({
      asset_class: assetClass,
      target_pct: text(form, `target_${assetClass}`),
      band_pct: text(form, `band_${assetClass}`) || "5",
    }))
    .filter((row) => row.target_pct !== "" && row.target_pct !== "0");
  return run(() => call("PUT", hh(householdId, "/portfolio/targets"), { targets }));
}

// --- F25 alternative investments ------------------------------------------------------

function dueDiligence(form: FormData, checklist: string[]) {
  const answers: Record<string, boolean | string> = {};
  for (const item of checklist) answers[item] = checked(form, `dd_${item}`);
  const promised = optional(form, "dd_promised_return_pct");
  if (promised) answers.promised_return_pct = promised;
  return answers;
}

export async function addAltAssetAction(
  householdId: string,
  checklist: string[],
  _: FormState,
  form: FormData,
): Promise<FormState> {
  let id = "";
  const result = await run(async () => {
    const row = await call<{ id: string }>("POST", hh(householdId, "/alt-assets"), {
      type: text(form, "type"),
      name: text(form, "name"),
      purchase_date: optional(form, "purchase_date"),
      cost: text(form, "cost"),
      current_value: optional(form, "current_value"),
      counterparty: optional(form, "counterparty"),
      expected_exit_date: optional(form, "expected_exit_date"),
      liquidity: text(form, "liquidity"),
      notes: optional(form, "notes"),
      weight_grams: optional(form, "weight_grams"),
      karat: optional(form, "karat"),
      revaluation_months: Number(text(form, "revaluation_months") || "12"),
      shariah_flag: text(form, "shariah_flag") || "UNKNOWN",
      is_recoverable: checked(form, "is_recoverable"),
      due_diligence: dueDiligence(form, checklist),
      owners: owners(form),
    });
    id = row.id;
  });
  if (result.error) return result;
  return go(`/personal/assets/${id}`);
}

export async function updateAltAssetAction(
  householdId: string,
  id: string,
  checklist: string[],
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("PATCH", hh(householdId, `/alt-assets/${id}`), {
      name: optional(form, "name"),
      purchase_date: optional(form, "purchase_date"),
      cost: optional(form, "cost"),
      counterparty: optional(form, "counterparty"),
      expected_exit_date: optional(form, "expected_exit_date"),
      liquidity: optional(form, "liquidity"),
      notes: optional(form, "notes"),
      weight_grams: optional(form, "weight_grams"),
      karat: optional(form, "karat"),
      shariah_flag: optional(form, "shariah_flag"),
      is_recoverable: checked(form, "is_recoverable"),
      due_diligence: dueDiligence(form, checklist),
    }),
  );
}

export async function deleteAltAssetAction(householdId: string, id: string) {
  const result = await run(() => call("DELETE", hh(householdId, `/alt-assets/${id}`)));
  if (result.error) return result;
  return go("/personal/assets");
}

export async function addValuationAction(
  householdId: string,
  assetId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, `/alt-assets/${assetId}/valuations`), {
      date: text(form, "date"),
      value: text(form, "value"),
    }),
  );
}

export async function deleteValuationAction(householdId: string, assetId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/alt-assets/${assetId}/valuations/${id}`)));
}

export async function addCashFlowAction(
  householdId: string,
  assetId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const amount = text(form, "amount");
  // The form asks for a positive amount and a direction; the API wants a signed amount.
  const signed = text(form, "direction") === "OUT" && amount !== "" ? `-${amount}` : amount;
  return run(() =>
    call("POST", hh(householdId, `/alt-assets/${assetId}/cash-flows`), {
      date: text(form, "date"),
      amount: signed,
      type: text(form, "type"),
      note: optional(form, "note"),
    }),
  );
}

export async function deleteCashFlowAction(householdId: string, assetId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/alt-assets/${assetId}/cash-flows/${id}`)));
}

export async function uploadDocumentAction(
  householdId: string,
  assetId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const file = form.get("file");
  if (!(file instanceof File) || file.size === 0) return { error: "VALIDATION" };
  const content = Buffer.from(await file.arrayBuffer()).toString("base64");
  return run(() =>
    call("POST", hh(householdId, `/alt-assets/${assetId}/documents`), {
      type: text(form, "type") || "OTHER",
      filename: file.name,
      content_base64: content,
    }),
  );
}

export async function deleteDocumentAction(householdId: string, assetId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/alt-assets/${assetId}/documents/${id}`)));
}

// --- F13 Zakat and tax ----------------------------------------------------------------

export async function createZakatAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  let id = "";
  const result = await run(async () => {
    const row = await call<{ data: { id: string } }>("POST", hh(householdId, "/zakat/snapshots"), {
      member_id: text(form, "member_id"),
      date: optional(form, "date"),
      nisab_basis: optional(form, "nisab_basis"),
      price_per_gram: optional(form, "price_per_gram"),
      shares_method: optional(form, "shares_method"),
    });
    id = row.data.id;
  });
  if (result.error) return result;
  return go(`/personal/zakat/${id}`);
}

export async function deleteZakatAction(householdId: string, id: string) {
  const result = await run(() => call("DELETE", hh(householdId, `/zakat/snapshots/${id}`)));
  if (result.error) return result;
  return go("/personal/zakat");
}

export async function createTaxAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  let id = "";
  const result = await run(async () => {
    const row = await call<{ data: { id: string } }>("POST", hh(householdId, "/tax/snapshots"), {
      member_id: text(form, "member_id"),
      tax_year: text(form, "tax_year"),
      salary_income: optional(form, "salary_income"),
      other_income: optional(form, "other_income"),
    });
    id = row.data.id;
  });
  if (result.error) return result;
  return go(`/personal/tax/${id}`);
}

export async function deleteTaxAction(householdId: string, id: string) {
  const result = await run(() => call("DELETE", hh(householdId, `/tax/snapshots/${id}`)));
  if (result.error) return result;
  return go("/personal/tax");
}

// --- F17 FIRE and F18 scenarios ------------------------------------------------------

export async function createFirePlanAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  let id = "";
  const result = await run(async () => {
    const row = await call<{ id: string }>("POST", hh(householdId, "/fire/plan"), {
      name: text(form, "name"),
      member_id: optional(form, "member_id"),
      net_worth: text(form, "net_worth"),
      monthly_savings: text(form, "monthly_savings"),
      yearly_expenses: text(form, "yearly_expenses"),
      nominal_return_pct: text(form, "nominal_return_pct"),
      inflation_pct: text(form, "inflation_pct"),
      withdrawal_rate_pct: text(form, "withdrawal_rate_pct"),
      current_age: Number(text(form, "current_age")),
      include_illiquid: checked(form, "include_illiquid"),
    });
    id = row.id;
  });
  if (result.error) return result;
  return go(`/personal/fire/${id}`);
}

export async function deleteFirePlanAction(householdId: string, id: string) {
  const result = await run(() => call("DELETE", hh(householdId, `/fire/plans/${id}`)));
  if (result.error) return result;
  return go("/personal/fire");
}

const SCENARIO_PARAM: Record<string, string> = {
  MARKET_CRASH: "fall_pct",
  EXPENSES_UP: "pct",
  RETIRE_EARLIER: "years",
  INFLATION_SHOCK: "points",
};

export async function runScenarioAction(
  householdId: string,
  planId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const preset = text(form, "preset");
  const params: Record<string, string> = {};
  if (preset === "EVENT_REPLAY") {
    params.event_id = text(form, "event_id");
  } else {
    const name = SCENARIO_PARAM[preset];
    const value = optional(form, "value");
    if (name && value) params[name] = value;
  }
  return run(() =>
    call("POST", hh(householdId, "/fire/scenarios"), { plan_id: planId, preset, params }),
  );
}

export async function deleteScenarioAction(householdId: string, planId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/fire/plans/${planId}/scenarios/${id}`)));
}

// --- F19 goals ------------------------------------------------------------------------

export async function addGoalAction(
  householdId: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  return run(() =>
    call("POST", hh(householdId, "/goals"), {
      type: text(form, "type"),
      name: text(form, "name"),
      member_id: optional(form, "member_id"),
      target_amount: optional(form, "target_amount"),
      target_date: optional(form, "target_date"),
      target_age: optional(form, "target_age"),
    }),
  );
}

export async function setGoalActiveAction(householdId: string, id: string, active: boolean) {
  return run(() => call("PATCH", hh(householdId, `/goals/${id}`), { is_active: active }));
}

export async function deleteGoalAction(householdId: string, id: string) {
  return run(() => call("DELETE", hh(householdId, `/goals/${id}`)));
}

// --- F20 alerts -----------------------------------------------------------------------

export async function setAlertRuleAction(
  alertType: string,
  _: FormState,
  form: FormData,
): Promise<FormState> {
  const params: Record<string, string> = {};
  for (const [key, value] of form.entries()) {
    if (key.startsWith("param_") && typeof value === "string" && value.trim() !== "") {
      params[key.slice(6)] = value.trim();
    }
  }
  return run(() =>
    call("PUT", `/alerts/${alertType}`, {
      channel: text(form, "channel") || "EMAIL",
      frequency: text(form, "frequency") || "DAILY_DIGEST",
      is_active: checked(form, "is_active"),
      params: Object.keys(params).length ? params : undefined,
    }),
  );
}

export async function markNotificationsReadAction(id?: string) {
  return run(() => call("POST", "/notifications/read", { id: id ?? null }));
}
