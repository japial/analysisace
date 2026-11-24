/**
 * Shapes of the personal finance API (F12 to F26), kept in step with
 * backend/app/schemas/personal.py and the summary endpoints in backend/app/api/v1.
 *
 * Money, percentages and units are decimal strings. Dates are "YYYY-MM-DD".
 */

export type Decimal = string;

export type HouseholdRole = "OWNER" | "EDITOR" | "VIEWER";

export interface Household {
  id: string;
  name: string;
  role: HouseholdRole;
  member_id: string;
}

export interface Member {
  id: string;
  display_name: string;
  role: HouseholdRole;
  birth_year: number | null;
  hawl_date: string | null;
  nisab_basis: NisabBasis | null;
  has_login: boolean;
  is_you: boolean;
}

export interface OwnerShare {
  pct: Decimal;
  member_id: string | null;
  external_name: string | null;
}

// --- F12 costs ------------------------------------------------------------------------

export interface Category {
  id: string;
  key: string;
  name_en: string;
  name_bn: string;
  is_default: boolean;
}

export interface Expense {
  id: string;
  date: string;
  amount: Decimal;
  category_id: string;
  note: string | null;
  member_id: string | null;
  recurring_id: string | null;
}

export const RECURRING_FREQUENCIES = [
  "WEEKLY",
  "MONTHLY",
  "QUARTERLY",
  "HALF_YEARLY",
  "YEARLY",
] as const;
export type RecurringFrequency = (typeof RECURRING_FREQUENCIES)[number];

export interface RecurringRule {
  id: string;
  category_id: string;
  amount: Decimal;
  frequency: RecurringFrequency;
  start_date: string;
  end_date: string | null;
  note: string | null;
  member_id: string | null;
  is_active: boolean;
}

/** F27 income records. */
export interface IncomeEntry {
  id: string;
  date: string;
  amount: Decimal;
  kind: string;
  note: string | null;
  member_id: string | null;
  recurring_id: string | null;
}

export interface IncomeRule {
  id: string;
  kind: string;
  amount: Decimal;
  frequency: RecurringFrequency;
  start_date: string;
  end_date: string | null;
  note: string | null;
  member_id: string | null;
  is_active: boolean;
}

export interface IncomeSummary {
  as_of_date: string;
  /** The kinds a record may have, from the API's configuration. */
  kinds: string[];
  months: { month: string; income: Decimal; costs: Decimal; savings: Decimal }[];
  by_kind: { kind: string; total: Decimal }[];
  income_12m: Decimal;
  costs_12m: Decimal;
  savings_12m: Decimal;
  savings_rate_pct: Decimal | null;
  months_counted: number;
  average_monthly_income: Decimal | null;
  average_monthly_savings: Decimal | null;
}

export interface CostSummary {
  as_of_date: string;
  months: { month: string; total: Decimal; real_total: Decimal | null; by_category: Record<string, Decimal> }[];
  years: { year: number; total: Decimal }[];
  by_category: { category_id: string; total: Decimal }[];
  trailing_12_months: Decimal;
  price_base_month: string | null;
}

export interface ImportResult {
  imported: number;
  updated: number;
  /** One per bad row: its number as a spreadsheet shows it and a code such as BAD_DATE. */
  errors: { row?: number; code?: string; error?: string; [key: string]: unknown }[];
}

// --- F14 portfolio --------------------------------------------------------------------

export const ACCOUNT_TYPES = [
  "BO",
  "MUTUAL_FUND",
  "SAVINGS_CERTIFICATE",
  "FDR",
  "DPS",
  "PROVIDENT_FUND",
  "CASH",
  "ISLAMIC_BANK",
  "SUKUK",
  "FOREIGN_BROKERAGE",
  "OTHER",
] as const;
export type AccountType = (typeof ACCOUNT_TYPES)[number];

export const INSTRUMENT_TYPES = [
  "DSE_SHARE",
  "MUTUAL_FUND_UNIT",
  "SUKUK",
  "ISLAMIC_DEPOSIT",
  "SAVINGS_CERTIFICATE",
  "FDR",
  "DPS",
  "PROVIDENT_FUND",
  "CASH",
  "BANK_BALANCE",
  "FOREIGN_SECURITY",
  "OTHER",
] as const;
export type InstrumentType = (typeof INSTRUMENT_TYPES)[number];

export const TRANSACTION_TYPES = [
  "BUY",
  "SELL",
  "DEPOSIT",
  "WITHDRAWAL",
  "DIVIDEND",
  "PROFIT",
  "BONUS",
  "FEE",
  "TAX",
] as const;
export type TransactionType = (typeof TRANSACTION_TYPES)[number];

export const LIABILITY_TYPES = [
  "HOME_LOAN",
  "PERSONAL_LOAN",
  "CREDIT_CARD",
  "PRIVATE_DEBT",
  "OTHER",
] as const;
export type LiabilityType = (typeof LIABILITY_TYPES)[number];

export const PAYMENT_FREQUENCIES = [...RECURRING_FREQUENCIES, "AT_MATURITY"] as const;
export type PaymentFrequency = (typeof PAYMENT_FREQUENCIES)[number];

export interface Account {
  id: string;
  type: AccountType;
  institution: string;
  name: string;
  masked_number: string | null;
  is_active: boolean;
}

export interface Holding {
  id: string;
  account_id: string;
  instrument_type: InstrumentType;
  name: string;
  ticker: string | null;
  product_id: string | null;
  sukuk_issue_id: string | null;
  quantity: Decimal;
  cost: Decimal;
  manual_value: Decimal | null;
  start_date: string | null;
  maturity_date: string | null;
  expected_rate: Decimal | null;
  final_rate: Decimal | null;
  payment_frequency: PaymentFrequency | null;
  profit_received: Decimal;
  tax_deducted: Decimal;
  is_interest_bearing: boolean;
  is_active: boolean;
}

export interface Transaction {
  id: string;
  date: string;
  type: TransactionType;
  amount: Decimal;
  units: Decimal | null;
  note: string | null;
}

export interface Liability {
  id: string;
  type: LiabilityType;
  name: string;
  lender: string | null;
  outstanding: Decimal;
  due_within_year: Decimal;
  is_interest_bearing: boolean;
  end_date: string | null;
  is_active: boolean;
}

export type ShariahLabel = "COMPLIANT" | "NON_COMPLIANT" | "UNKNOWN" | "UNDER_REVIEW";

export interface Position {
  kind: "HOLDING" | "ALT_ASSET";
  id: string;
  name: string;
  type: string;
  asset_class: string;
  value: Decimal;
  household_value: Decimal;
  household_pct: Decimal;
  cost: Decimal;
  method: string;
  valued_on: string | null;
  account_id: string | null;
  institution: string | null;
  ticker: string | null;
  sector: string | null;
  liquidity: string | null;
  shariah: ShariahLabel;
  quantity: Decimal | null;
  owners: OwnerShare[];
}

export interface PortfolioSummary {
  as_of_date: string;
  assets: Decimal;
  liabilities: Decimal;
  net_worth: Decimal;
  by_class: { key: string; value: Decimal }[];
  by_member: {
    member_id: string;
    display_name: string;
    assets: Decimal;
    liabilities: Decimal;
    net_worth: Decimal;
  }[];
  positions: Position[];
  debts: (Liability & { household_outstanding: Decimal })[];
}

/** `GET /households/{id}/ace/summary`: Assets, Capital and Earnings in one view (D19). */
export interface AceSummary {
  assets: { total: Decimal; liabilities: Decimal; net_worth: Decimal };
  capital: { at_work: Decimal; share_of_assets_pct: Decimal | null };
  earnings: {
    income_trailing_12_months: Decimal;
    costs_trailing_12_months: Decimal;
    savings_trailing_12_months: Decimal;
    savings_rate_pct: Decimal | null;
    average_monthly_income: Decimal | null;
    average_monthly_cost: Decimal | null;
    average_monthly_savings: Decimal | null;
    months_counted: number;
  };
}

export interface NetWorthPoint {
  date: string;
  assets: Decimal;
  liabilities: Decimal;
  net_worth: Decimal;
  capital?: Decimal | null;
}

// --- F15 performance, F16 allocation ---------------------------------------------------

export interface ReturnFigures {
  start: string | null;
  end: string | null;
  twr_pct: Decimal | null;
  twr_annualised_pct: Decimal | null;
  volatility_pct: Decimal | null;
  max_drawdown_pct: Decimal | null;
  xirr_pct: Decimal | null;
  value: Decimal;
}

export interface Performance extends ReturnFigures {
  period: "1Y" | "3Y" | "5Y" | "ALL";
  account_id: string | null;
  benchmarks: { code: string; return_pct: Decimal | null; annualised_pct: Decimal | null }[];
  risk_free_pct: Decimal | null;
  risk_free_series: string | null;
  diversification: {
    holdings: number;
    top_n: number;
    top_weight_pct: Decimal | null;
    sector_herfindahl: Decimal | null;
    sectors: number;
  } | null;
  accounts: (ReturnFigures & { account_id: string; institution: string })[];
  /** Each point is indexed to 100 at the start; keys are "portfolio" and benchmark codes. */
  chart: ({ date: string } & Record<string, string>)[];
}

export interface AllocationSlice {
  key: string;
  value: Decimal;
  pct: Decimal;
  name?: string;
}

export interface Drift {
  asset_class: string;
  value: Decimal;
  actual_pct: Decimal;
  target_pct: Decimal;
  band_pct: Decimal;
  drift_pts: Decimal;
  outside_band: boolean;
  difference: Decimal;
}

export interface Allocation {
  total: Decimal;
  by_class: AllocationSlice[];
  by_sector: AllocationSlice[];
  by_holding: AllocationSlice[];
  by_shariah: AllocationSlice[];
  drift: Drift[];
  asset_classes: string[];
}

// --- F25 alternative investments ------------------------------------------------------

export const ALT_ASSET_TYPES = [
  "LAND",
  "FLAT",
  "PLOT",
  "RENTAL_PROPERTY",
  "GOLD",
  "SILVER",
  "BUSINESS_STAKE",
  "PARTNERSHIP",
  "AGRICULTURE",
  "PRIVATE_LOAN",
  "PRIVATE_EQUITY",
  "COLLECTIBLE",
  "FAMILY_HOME",
  "PERSONAL_CAR",
  "OTHER",
] as const;
export type AltAssetType = (typeof ALT_ASSET_TYPES)[number];

export const LIQUIDITY_LEVELS = ["<1M", "<1Y", ">1Y"] as const;
export type Liquidity = (typeof LIQUIDITY_LEVELS)[number];

export const SHARIAH_FLAGS = ["COMPLIANT", "NON_COMPLIANT", "UNKNOWN"] as const;
export type ShariahFlag = (typeof SHARIAH_FLAGS)[number];

export const CASH_FLOW_TYPES = [
  "RENT",
  "PROFIT_SHARE",
  "INSTALMENT",
  "CAPITAL_ADDED",
  "SALE_PROCEEDS",
  "OTHER",
] as const;
export type CashFlowType = (typeof CASH_FLOW_TYPES)[number];

export interface AltAsset {
  id: string;
  type: AltAssetType;
  name: string;
  purchase_date: string | null;
  cost: Decimal;
  counterparty: string | null;
  expected_exit_date: string | null;
  liquidity: Liquidity;
  notes: string | null;
  weight_grams: Decimal | null;
  karat: number | null;
  revaluation_months: number;
  shariah_flag: ShariahFlag;
  shariah_reason: string | null;
  zakat_rule: string | null;
  is_recoverable: boolean;
  due_diligence: Record<string, boolean | string> | null;
  is_active: boolean;
}

export interface AltAssetView extends AltAsset {
  value: Decimal;
  household_value: Decimal;
  household_pct: Decimal;
  value_method: string;
  valued_on: string | null;
  asset_class: string;
  xirr_pct: Decimal | null;
  cash_received: Decimal;
  revaluation_due: string | null;
  owners: OwnerShare[];
}

export interface Valuation {
  id: string;
  date: string;
  value: Decimal;
  method: string;
}

export interface CashFlow {
  id: string;
  date: string;
  amount: Decimal;
  type: CashFlowType;
  note: string | null;
}

export interface StoredDocument {
  id: string;
  type: string;
  filename: string;
  size_bytes: number;
  created_at: string;
}

export interface AltAssetDetail {
  asset: AltAssetView;
  valuations: Valuation[];
  cash_flows: CashFlow[];
  documents: StoredDocument[];
}

export interface DueDiligence {
  checklist: string[];
  tbill_yield_pct: Decimal | null;
  tbill_date: string | null;
}

// --- F26 sukuk and Islamic bank products ----------------------------------------------

export interface IslamicHolding extends Position {
  start_date: string | null;
  maturity_date: string | null;
  payment_frequency: string | null;
  rate_pct: Decimal | null;
  rate_is_final: boolean;
  profit_at_rate: Decimal | null;
  profit_received: Decimal;
  tax_deducted: Decimal;
  days_to_maturity: number | null;
}

export interface CalendarEntry {
  date: string;
  kind: "MATURITY" | "SUKUK_AUCTION" | string;
  name: string;
  instrument_type: string | null;
  institution: string | null;
  amount: Decimal | null;
  rate_pct: Decimal | null;
  individual_quota_pct?: Decimal | null;
  days_away: number;
}

export interface BankExposure {
  bank: string;
  amount: Decimal;
  share_pct: Decimal;
  status: "NORMAL" | "RESTRUCTURING" | "RESTRICTED";
  note_en: string | null;
  note_bn: string | null;
  source_links: { title: string; url: string }[];
  flag_updated_at: string | null;
}

export interface ProductComparison {
  tbill_pct: Decimal | null;
  tbill_date: string | null;
  inflation_pct: Decimal | null;
  inflation_date: string | null;
  rows: {
    kind: string;
    name: string;
    issuer: string;
    rate_pct: Decimal | null;
    real_rate_pct: Decimal | null;
    spread_over_tbill_pts: Decimal | null;
    tenor_months: number | null;
    min_amount: Decimal | null;
    rate_is_provisional: boolean;
    as_of: string;
  }[];
}

export interface SukukIssue {
  id: string;
  code: string;
  name: string;
  issuer: string;
  structure: string;
  is_government: boolean;
  ticker: string | null;
  issue_date: string | null;
  maturity_date: string | null;
  rate_pct: Decimal | null;
  payment_frequency: string | null;
  min_investment: Decimal | null;
  auction_date: string | null;
  individual_quota_pct: Decimal | null;
}

// --- F13 Zakat and tax ----------------------------------------------------------------

export type NisabBasis = "GOLD" | "SILVER";

export interface ZakatItem {
  label: string;
  asset_kind: "HOLDING" | "ALT_ASSET" | "LIABILITY";
  asset_id: string;
  rule: string;
  treatment: string;
  value: Decimal;
  owner_pct: Decimal;
  zakatable: Decimal;
  flags: string[];
}

export interface ZakatSnapshot {
  id: string;
  member_id: string;
  date: string;
  nisab_basis: NisabBasis;
  price_per_gram: Decimal;
  nisab_value: Decimal;
  shares_method: "MARKET_VALUE" | "ZAKATABLE_ASSETS";
  items: ZakatItem[];
  total_zakatable: Decimal;
  total_deductions: Decimal;
  net_zakatable: Decimal;
  zakat_due: Decimal;
  config_version: string;
  created_at: string;
}

export interface RecordedIncomeBasis {
  salary: "RECORDS" | "ENTERED";
  other: "RECORDS" | "ENTERED";
  not_counted: { kind: string; amount: Decimal }[];
  unassigned: Decimal;
}

/** `GET /tax/recorded-income`: what a statement would take from the income records. */
export interface RecordedIncome {
  tax_year: string;
  salary: Decimal;
  other: Decimal;
  not_counted: { kind: string; amount: Decimal }[];
  unassigned: Decimal;
}

export interface TaxItems {
  period: { start: string; end: string };
  assets: { label: string; category: string; type: string; owner_pct: Decimal; cost: Decimal; value: Decimal }[];
  liabilities: { label: string; type: string; owner_pct: Decimal; outstanding: Decimal }[];
  totals: {
    assets_cost: Decimal;
    assets_value: Decimal;
    liabilities: Decimal;
    net_wealth_cost: Decimal;
    income: Decimal;
  };
  income: Record<string, Decimal>;
  /** Where salary and other income came from (FR27.5). Missing on statements made before F27. */
  income_basis?: RecordedIncomeBasis;
  tax_deducted: { in_year: Decimal; recorded_on_holdings: Decimal; lines: Record<string, unknown>[] };
  rebate_eligible: { label: string; amount?: Decimal; [key: string]: unknown }[];
  rebate_eligible_total: Decimal;
}

export interface TaxSnapshot {
  id: string;
  member_id: string;
  tax_year: string;
  as_of: string;
  items: TaxItems;
  created_at: string;
}

// --- F17 FIRE, F18 scenarios, F19 goals -----------------------------------------------

export interface ProjectionPoint {
  year: number;
  age: Decimal;
  net_worth: Decimal;
}

/** `GET /households/{id}/ace/trend` (D23). Null means no record for that month, not zero. */
export interface AceTrendMonth {
  month: string;
  snapshot_date: string | null;
  net_worth: Decimal | null;
  assets: Decimal | null;
  capital: Decimal | null;
  capital_share_pct: Decimal | null;
  income: Decimal | null;
  costs: Decimal | null;
  savings: Decimal | null;
  savings_rate_pct: Decimal | null;
}

export interface AceTrend {
  months: AceTrendMonth[];
  /** Last month with a value less the first; null with fewer than two. */
  change: { net_worth: Decimal | null; capital: Decimal | null; savings_total: Decimal | null };
}

/** D22 guided set-up. */
export type SetupStep = "you" | "income" | "costs" | "savings" | "plan";

export interface SetupStatus {
  steps: { key: SetupStep; done: boolean }[];
  done: number;
  total: number;
  complete: boolean;
  /** Default expense category keys the quick start asks about. */
  fixed_categories: string[];
  variable_categories: string[];
  /** Savings kinds from the API's configuration. */
  savings_kinds: string[];
}

/** `GET /households/{id}/fire/progress`: the overview's FIRE panel (D21). */
export interface FireProgress {
  /** PLAN: newest plan. ESTIMATE: no plan, FIRE number from a year of costs. NO_COSTS: nothing to go on. */
  basis: "PLAN" | "ESTIMATE" | "NO_COSTS";
  plan: {
    id: string;
    name: string;
    computed_at: string;
    fire_age: Decimal | null;
    current_age: Decimal | null;
    years_to_fire: Decimal | null;
  } | null;
  fire_number: Decimal | null;
  yearly_costs: Decimal | null;
  /** Months with cost records behind `yearly_costs` (up to 12). */
  cost_months: number;
  withdrawal_rate_pct: Decimal;
  investable: Decimal;
  include_illiquid: boolean;
  progress_pct: Decimal | null;
  gap: Decimal | null;
  savings_rate_pct: Decimal | null;
  average_monthly_savings: Decimal | null;
}

export interface FireDefaults {
  net_worth: Decimal;
  total_net_worth: Decimal;
  illiquid_excluded: Decimal;
  include_illiquid: boolean;
  yearly_expenses: Decimal;
  monthly_savings: Decimal | null;
  inflation_pct: Decimal | null;
  inflation_months: number;
  nominal_return_pct: Decimal | null;
  nominal_return_basis: string;
  withdrawal_rate_pct: Decimal;
  current_age: number | null;
  market_share_pct: Decimal;
  max_age: number;
}

export interface FirePlan {
  id: string;
  member_id: string | null;
  name: string;
  inputs: Record<string, string | boolean>;
  fire_number: Decimal;
  fire_age: Decimal | null;
  projection: ProjectionPoint[];
  computed_at: string;
}

export const SCENARIO_PRESETS = [
  "MARKET_CRASH",
  "EVENT_REPLAY",
  "EXPENSES_UP",
  "RETIRE_EARLIER",
  "INFLATION_SHOCK",
] as const;
export type ScenarioPreset = (typeof SCENARIO_PRESETS)[number];

export interface Scenario {
  id: string;
  fire_plan_id: string;
  preset: ScenarioPreset;
  params: Record<string, string>;
  result: {
    fire_number: Decimal;
    fire_age: Decimal | null;
    base_fire_age: Decimal | null;
    fire_age_change: Decimal | null;
    worst_year_net_worth: Decimal;
    base_worst_year_net_worth: Decimal;
    depleted_age: Decimal | null;
    projection: ProjectionPoint[];
  };
  computed_at: string;
}

export interface FirePlanDetail {
  plan: FirePlan;
  scenarios: Scenario[];
}

export interface MarketEvent {
  id: string;
  slug: string;
  type: string;
  t0: string;
  title_en: string;
  title_bn: string;
}

export const GOAL_TYPES = ["NET_WORTH", "INVESTED_AMOUNT", "MONTHLY_SAVINGS", "FIRE_AGE"] as const;
export type GoalType = (typeof GOAL_TYPES)[number];

export interface Goal {
  id: string;
  type: GoalType;
  name: string;
  member_id: string | null;
  target_amount: Decimal | null;
  target_date: string | null;
  target_age: number | null;
  achieved_at: string | null;
  is_active: boolean;
}

export interface GoalProgress {
  goal: Goal;
  current: Decimal | null;
  target: Decimal | null;
  progress_pct: Decimal | null;
  reached: boolean;
  on_track: boolean | null;
  days_left: number | null;
}

// --- F20 alerts, F21 community --------------------------------------------------------

export const ALERT_TYPES = [
  "ALLOCATION_DRIFT",
  "VOLATILITY",
  "GOAL_REACHED",
  "MATURITY_DUE",
  "REVALUATION_DUE",
  "HAWL_APPROACHING",
  "MONTHLY_REPORT",
  // Market alerts (F7). Shariah status reaches holders and watchers; the other two are opt-in.
  "SHARIAH_STATUS",
  "REGIME_CHANGE",
  "SHOCK_EVENT",
] as const;
export type PersonalAlertType = (typeof ALERT_TYPES)[number];

export type AlertChannel = "EMAIL" | "PUSH" | "BOTH";
export type AlertFrequency = "INSTANT" | "DAILY_DIGEST";

export interface AlertRule {
  type: string;
  channel: AlertChannel;
  frequency: AlertFrequency;
  is_active: boolean;
  params: Record<string, string | number>;
}

export interface Notification {
  id: string;
  type: string;
  message_key: string;
  data: Record<string, string | number | null>;
  link: string | null;
  created_at: string;
  read_at: string | null;
}

export interface Notifications {
  items: Notification[];
  unread: number;
}

export interface CommunityBenchmarks {
  min_group_size: number;
  has_plan: boolean;
  age_band: [number, number] | null;
  group_size_met: boolean;
  you: { savings_rate_pct: Decimal | null; fire_progress_pct: Decimal } | null;
  group: {
    size_at_least: number;
    median_savings_rate_pct: Decimal | null;
    median_fire_progress_pct: Decimal;
  } | null;
}
