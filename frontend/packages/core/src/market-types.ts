/**
 * Shapes of the market layer responses (F1 to F8) and its admin screens.
 * Kept in step with backend/app/schemas/market.py. Decimals are strings.
 */

export type ShariahStatus = "COMPLIANT" | "NON_COMPLIANT" | "UNDER_REVIEW";

export interface SeriesPoint {
  date: string;
  value: string;
}

export interface Series {
  code: string;
  points: SeriesPoint[];
}

// --- F1 -------------------------------------------------------------------------------

export interface RuleResult {
  rule: string;
  value_pct?: string | null;
  threshold_pct?: string;
  passed?: boolean | null;
  note?: string | null;
  /** Only on the `market_cap_average` row. */
  value?: string;
  months?: number;
}

export interface ShariahResult {
  id: string;
  period_end: string;
  method: string;
  method_version: string;
  status: ShariahStatus;
  ratios: RuleResult[];
  reasons: string[];
  screened_at: string;
}

export interface Financials {
  id: string;
  ticker: string;
  period_end: string;
  period_type: string;
  total_debt_interest_bearing: string | null;
  cash_and_interest_securities: string | null;
  receivables: string | null;
  total_revenue: string | null;
  non_permissible_income: string | null;
  zakatable_assets: string | null;
  shares_outstanding: number | null;
  source_id: string;
  source_page: number | null;
  reviewed_at: string | null;
  source_name: string | null;
  source_url: string | null;
}

export interface Classification {
  stage1_pass: boolean;
  activity: string | null;
  reason: string;
  method_version: string;
}

export interface StatusChange {
  from_status: string | null;
  to_status: string;
  cause: "SCREEN" | "OVERRIDE";
  changed_at: string;
}

export interface CompanyShariah {
  ticker: string;
  status: ShariahStatus;
  screen_status: ShariahStatus;
  method: string;
  method_version: string;
  screened_at: string;
  override_status: ShariahStatus | null;
  override_reason: string | null;
  board_note: string | null;
  non_permissible_income_ratio: string | null;
  classification: Classification | null;
  results: ShariahResult[];
  financials: Financials | null;
  history: StatusChange[];
  config_approved: boolean;
}

export interface ShariahListItem {
  ticker: string;
  name: string;
  sector: string | null;
  status: ShariahStatus;
  method_version: string;
  screened_at: string;
  market_cap: string | null;
  overridden: boolean;
}

export interface Basket {
  years: number;
  start: string | null;
  members: string[];
  series: Record<string, SeriesPoint[]>;
}

// --- F3 -------------------------------------------------------------------------------

export type Confidence = "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";

export interface Score {
  subject_type: "TICKER" | "SECTOR";
  subject: string;
  score_type: "RATE_SENSITIVITY" | "RATE_SENSITIVITY_NO_MARKET";
  value: string | null;
  std_error: string | null;
  t_stat: string | null;
  confidence: Confidence;
  n_obs: number;
  sample_start: string | null;
  sample_end: string | null;
  computed_at: string;
}

export interface RatesOverview {
  latest_auctions: { code: string; date: string; value: string }[];
  yield_trend: SeriesPoint[];
  sectors: Score[];
}

// --- F5 -------------------------------------------------------------------------------

export type EventType = "WAR" | "ENERGY" | "POLITICAL" | "POLICY" | "OTHER";
export const EVENT_TYPES: readonly EventType[] = ["WAR", "ENERGY", "POLITICAL", "POLICY", "OTHER"];

export interface ShockEvent {
  id: string;
  slug: string;
  type: EventType;
  t0: string;
  title_en: string;
  title_bn: string;
  description_en: string;
  description_bn: string;
  source_links: { label: string; url: string }[];
  published: boolean;
}

export interface EventMetric {
  subject_type: "TICKER" | "SECTOR" | "INDEX";
  subject: string;
  ret_1: string | null;
  ret_5: string | null;
  ret_20: string | null;
  max_dd_60: string | null;
  sessions_to_recover: number | null;
  computed_at: string;
}

export interface EventDetail {
  event: ShockEvent;
  metrics: EventMetric[];
  similar: ShockEvent[];
}

export interface CompanyEvent {
  event: ShockEvent;
  metric: EventMetric;
}

// --- F4 -------------------------------------------------------------------------------

export interface NoteFigure {
  code: string;
  kind: "level" | "index";
  unit: string;
  value: string;
  previous: string | null;
  change: string | null;
  change_pct: string | null;
  as_of: string;
  source_id: string;
  source_name: string | null;
  source_url: string | null;
}

export interface MacroNote {
  id: string;
  week_start: string;
  locale: "en" | "bn";
  status: "DRAFT" | "PUBLISHED";
  title: string;
  body: string;
  figures: NoteFigure[];
  published_at: string | null;
}

export type MacroNoteSummary = Omit<MacroNote, "body" | "figures">;

// --- F8 -------------------------------------------------------------------------------

export interface RegimeMonth {
  month: string;
  label: string;
  components: Record<string, string | null>;
  config_version: string;
}

export interface Regime {
  current: RegimeMonth | null;
  history: RegimeMonth[];
  sectors: { sector: string; avg_monthly_return: string; hit_rate: string; n_months: number }[];
  min_months: number;
}

// --- F6 -------------------------------------------------------------------------------

export interface MarketCheck {
  as_of_day: string;
  listed_value: string;
  holdings: {
    holding_id: string;
    name: string;
    ticker: string;
    sector: string | null;
    value: string;
    weight_pct: string;
    shariah: string;
    rate_sensitivity_pct: string | null;
    rate_confidence: Confidence | null;
    dividends_12m: string;
    non_permissible_income_ratio: string | null;
    /** The same ratio as a percent, for display. */
    non_permissible_income_pct: string | null;
    purification: string | null;
  }[];
  shariah_share: { status: string; weight_pct: string }[];
  rate_sensitivity: { weighted_pct: string | null; coverage_pct: string };
  shock_exposure: {
    event_id: string;
    slug: string;
    type: EventType;
    t0: string;
    title_en: string;
    title_bn: string;
    ret_1: string | null;
    ret_5: string | null;
    ret_20: string | null;
    max_dd_60: string | null;
    coverage_pct: string;
  }[];
  purification: { total: string; dividends_unknown_ratio: string };
}

export interface WatchItem {
  ticker: string;
  name: string;
  status: ShariahStatus | null;
}

// --- admin ----------------------------------------------------------------------------

export interface DataIssue {
  id: string;
  check_name: string;
  dataset: string;
  entity: string | null;
  date: string | null;
  detail: string;
  status: "OPEN" | "RESOLVED" | "IGNORED";
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface DataIssues {
  items: DataIssue[];
  total: number;
  limit: number;
  offset: number;
  open_by_dataset: Record<string, number>;
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  entity: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  at: string;
}

export interface JobRun {
  id: string;
  job: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  detail: Record<string, unknown> | null;
}

export interface CorporateActionRow {
  id: string;
  ticker: string;
  ex_date: string;
  type: string;
  ratio: string | null;
  amount: string | null;
}

export interface ShariahAdminItem {
  ticker: string;
  name: string;
  sector: string | null;
  status: ShariahStatus | null;
  screen_status: ShariahStatus | null;
  override_status: ShariahStatus | null;
  override_reason: string | null;
  board_note: string | null;
  classification: Classification | null;
  unreviewed_financials: number;
}

export const FINANCIAL_FIGURES = [
  "total_debt_interest_bearing",
  "cash_and_interest_securities",
  "receivables",
  "total_revenue",
  "non_permissible_income",
  "zakatable_assets",
] as const;

export const STAGE1_ACTIVITIES = [
  "conventional_banking",
  "conventional_insurance",
  "interest_based_lending",
  "alcohol",
  "tobacco",
  "pork",
  "gambling",
  "adult_entertainment",
  "weapons",
] as const;

/** Admin notice about a bank (FR26.5). */
export interface BankFlag {
  id: string;
  bank: string;
  status: "NORMAL" | "RESTRUCTURING" | "RESTRICTED";
  note_en: string;
  note_bn: string;
  source_links: { title: string; url: string }[];
  updated_at: string;
}

export const BANK_STATUSES = ["NORMAL", "RESTRUCTURING", "RESTRICTED"] as const;
