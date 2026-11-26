/**
 * Server-side access to the analysisACE API. Pages and server actions call these, so the
 * browser never talks to the API or sees a session token.
 */
import type {
  AuthResult,
  Company,
  CompanyDetail,
  Envelope,
  OptionalConsent,
  Page,
  Role,
  RolesResponse,
  User,
} from "@analysisace/core";

const API_BASE = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// Market data changes once a day, after the close, so production caches public responses
// for five minutes. Development never caches, so newly loaded data shows up at once.
const REVALIDATE_SECONDS = 300;
const PUBLIC_CACHING: RequestInit =
  process.env.NODE_ENV === "development"
    ? { cache: "no-store" }
    : { next: { revalidate: REVALIDATE_SECONDS } };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    /** Stable error code from the API, such as "EMAIL_TAKEN". Translated under `errors`. */
    readonly code: string,
    path: string,
  ) {
    super(`API responded ${status} (${code}) for ${path}`);
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Session token. Requests with a token are never cached. */
  token?: string;
  userAgent?: string | null;
  /** The visitor's address, passed on so the API can rate-limit per visitor (D28). */
  forwardedFor?: string | null;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, userAgent, forwardedFor } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  if (userAgent) headers["User-Agent"] = userAgent;
  if (forwardedFor) headers["X-Forwarded-For"] = forwardedFor;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      ...(method === "GET" && !token ? PUBLIC_CACHING : { cache: "no-store" as const }),
    });
  } catch {
    throw new ApiError(503, "UNAVAILABLE", path);
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = (payload as { detail?: unknown } | null)?.detail;
    const code =
      typeof detail === "string" ? detail : response.status === 422 ? "VALIDATION" : "UNAVAILABLE";
    throw new ApiError(response.status, code, path);
  }
  if (response.status === 204 || response.status === 202) return undefined as T;
  return (await response.json()) as T;
}

/**
 * The raw API response, for file downloads (CSV exports, stored documents) that a route
 * handler passes on to the browser unchanged.
 */
export async function requestRaw(path: string, token: string): Promise<Response> {
  return fetch(`${API_BASE}/api/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
}

// --- Public market data ---------------------------------------------------------------

export function listCompanies(params: {
  q?: string;
  limit?: number;
}): Promise<Envelope<Page<Company>>> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.size ? `?${query}` : "";
  return request(`/companies${suffix}`);
}

/** Returns null when the ticker does not exist. */
export async function getCompany(ticker: string): Promise<Envelope<CompanyDetail> | null> {
  try {
    return await request(`/companies/${encodeURIComponent(ticker)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

// --- Accounts -------------------------------------------------------------------------

export function register(
  body: {
    email: string;
    password: string;
    full_name: string;
    locale: string;
    accept_terms: boolean;
  },
  userAgent: string | null,
  forwardedFor: string | null = null,
): Promise<AuthResult> {
  return request("/auth/register", { method: "POST", body, userAgent, forwardedFor });
}

export function login(
  body: { email: string; password: string },
  userAgent: string | null,
  forwardedFor: string | null = null,
): Promise<AuthResult> {
  return request("/auth/login", {
    method: "POST",
    body: { ...body, client: "web" },
    userAgent,
    forwardedFor,
  });
}

export function logout(token: string): Promise<void> {
  return request("/auth/logout", { method: "POST", token });
}

export function requestPasswordReset(email: string, forwardedFor: string | null = null): Promise<void> {
  return request("/auth/password-reset/request", { method: "POST", body: { email }, forwardedFor });
}

export function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  return request("/auth/password-reset/confirm", {
    method: "POST",
    body: { token, new_password: newPassword },
  });
}

export function requestEmailVerification(token: string): Promise<void> {
  return request("/auth/verify-email/request", { method: "POST", token });
}

export function confirmEmailVerification(token: string): Promise<void> {
  return request("/auth/verify-email/confirm", { method: "POST", body: { token } });
}

export function getMe(token: string): Promise<User> {
  return request("/me", { token });
}

export function updateMe(
  token: string,
  body: { full_name?: string; locale?: string },
): Promise<User> {
  return request("/me", { method: "PATCH", body, token });
}

export function changePassword(
  token: string,
  body: { current_password: string; new_password: string },
): Promise<void> {
  return request("/me/password", { method: "POST", body, token });
}

export function updateConsents(
  token: string,
  consents: Partial<Record<OptionalConsent, boolean>>,
): Promise<User> {
  return request("/me/consents", { method: "PATCH", body: { consents }, token });
}

export function exportMe(token: string): Promise<Record<string, unknown>> {
  return request("/me/export", { token });
}

export function deleteMe(token: string, password: string): Promise<void> {
  return request("/me", { method: "DELETE", body: { password }, token });
}

// --- User management (permission USERS_MANAGE) ----------------------------------------

export function listUsers(
  token: string,
  params: { q?: string; role?: Role; limit: number; offset: number },
): Promise<Page<User>> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
  });
  if (params.q) query.set("q", params.q);
  if (params.role) query.set("role", params.role);
  return request(`/admin/users?${query}`, { token });
}

export function updateUser(
  token: string,
  userId: string,
  body: { role?: Role; is_active?: boolean },
): Promise<User> {
  return request(`/admin/users/${encodeURIComponent(userId)}`, { method: "PATCH", body, token });
}

export function listRoles(token: string): Promise<RolesResponse> {
  return request("/admin/roles", { token });
}
