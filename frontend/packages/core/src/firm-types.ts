/** Firm accounts, seats and API keys (F9, D30). */

export type FirmRole = "ADMIN" | "MEMBER";

export interface FirmSummary {
  id: string;
  name: string;
  role: FirmRole;
}

export interface FirmMember {
  user_id: string;
  full_name: string;
  email: string;
  role: FirmRole;
  since: string;
}

export interface FirmApiKey {
  id: string;
  name: string;
  prefix: string;
  rate_limit_per_minute: number;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface FirmApiKeyCreated extends FirmApiKey {
  /** Shown once, at creation; only a hash is stored. */
  key: string;
}

export interface FirmUsageRow {
  date: string;
  key: string;
  endpoint: string;
  calls: number;
}

export interface FirmDetail {
  id: string;
  name: string;
  role: FirmRole;
  seat_limit: number;
  report_disclaimer: string | null;
  has_logo: boolean;
  members: FirmMember[];
  /** Empty for members; only admins see keys and usage. */
  api_keys: FirmApiKey[];
  usage: FirmUsageRow[];
  /** Weeks with a published note, newest first. */
  report_weeks: string[];
}

export interface AdminFirm {
  id: string;
  name: string;
  seat_limit: number;
  seats_used: number;
  is_active: boolean;
  created_at: string;
}
