/**
 * Shapes of the API responses used by the clients.
 *
 * Written by hand for now and kept in step with backend/app/schemas. Replace with a client
 * generated from /api/v1/openapi.json once the API surface grows (see docs/ROADMAP.md).
 */

export interface SourceRef {
  name: string;
  url: string | null;
  fetched_at: string;
}

/** Every data-derived response carries when the data is from and where it came from. */
export interface Envelope<T> {
  data: T;
  as_of: string | null;
  sources: SourceRef[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Company {
  ticker: string;
  name: string;
  sector: string | null;
  listing_date: string | null;
  is_active: boolean;
}

export interface LatestPrice {
  date: string;
  /** Decimal string in taka. */
  close: string;
  adj_close: string | null;
  volume: number | null;
}

export interface CompanyDetail extends Company {
  latest_price: LatestPrice | null;
}

export type Role = "USER" | "ANALYST" | "ADMIN";

export type Permission =
  | "DATA_REVIEW"
  | "CONTENT_PUBLISH"
  | "SHARIAH_OVERRIDE"
  | "CONFIG_MANAGE"
  | "USERS_MANAGE"
  | "AUDIT_VIEW";

/** Consents a user can grant or withdraw at any time. TERMS is set at sign-up. */
export type OptionalConsent = "MARKETING" | "RELIGIOUS_PREFERENCES" | "COMMUNITY_BENCHMARKING";

export interface ConsentRecord {
  granted: boolean;
  at: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  locale: "bn" | "en";
  role: Role;
  is_active: boolean;
  consents: Partial<Record<OptionalConsent | "TERMS", ConsentRecord>>;
  created_at: string;
  last_login_at: string | null;
  permissions: Permission[];
}

/** Returned once at sign-in or sign-up. `token` is sent back as a Bearer header. */
export interface AuthResult {
  user: User;
  token: string;
  expires_at: string;
}

export interface RoleDefinition {
  role: Role;
  permissions: Permission[];
}

export interface RolesResponse {
  roles: RoleDefinition[];
  permissions: Permission[];
}
