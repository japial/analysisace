# Architecture

How the system is put together today. The product spec is [PRD.md](PRD.md); reasons for choices are in [DECISIONS.md](DECISIONS.md); progress is in [ROADMAP.md](ROADMAP.md).

## Overview

```
Public sources ──> adapters ──> ingestion services ──> PostgreSQL <── analytics jobs
 (DSE, Bangladesh Bank,          (quality checks,          │
  BBS, company reports)           data_issue queue)        │
                                                     FastAPI  /api/v1
                                                           │
                                         Next.js web app (server-rendered, bn/en)
                                         Expo mobile app (later, same packages)
```

Three processes run from the backend code, plus the web app:

| Process | Start command | Job |
|-|-|-|
| API | `uvicorn app.main:app` | Serves precomputed data. Does no heavy computation on request. |
| Worker | `python -m app.jobs.worker` | Runs scheduled ingestion and analytics jobs; records each run in `job_run`. |
| Migrations | `alembic upgrade head` | Runs once before the API and worker start. |
| Web | `next start` (or `node apps/web/server.js` in Docker) | Renders pages on the server and calls the API from there. |

## Data flow for market data

1. The worker fires a job on the schedule in `config/schedules.yaml` (Asia/Dhaka time).
2. An **adapter** (`backend/app/ingestion/adapters/`) fetches and parses one source into a batch of plain dataclasses, with a `SourceInfo` saying where and when it was fetched. Adapters never touch the database, so a source can be swapped for a licensed feed.
3. An **ingestion service** (`backend/app/services/`) runs quality checks, stores one `source` row for the fetch, and upserts the valid rows with that `source_id`. Rows that fail a check are not stored; each failure becomes a `data_issue` row for the admin review queue.
4. **Analytics jobs** read stored rows and write derived tables (adjusted prices now; Shariah results, sensitivity scores and event metrics in later milestones). Formulas live in `backend/app/analytics/` as pure functions.
5. The **API** reads the stored and derived rows. Each data-derived response is wrapped in an envelope:

```json
{ "data": { ... }, "as_of": "2026-11-12T11:00:00Z", "sources": [{ "name": "...", "url": "...", "fetched_at": "..." }] }
```

`as_of` is the fetch time of the newest source behind the data. This is how every number shown to a user stays traceable.

## Configuration

Two kinds of configuration, kept apart:

- **Environment variables** (`backend/app/core/config.py`): database URL, CORS origins, environment name. Secrets go here, never in the repo.
- **Business rules** (`config/*.yaml`): Shariah thresholds, Zakat rules, regime rules, schedules, excluded periods, trading calendar. Each file has a `version`. At start-up the worker stores any new version in the `config_version` table and refuses to continue if a file changed without a version bump. Derived results record the config version they used.

## Database

PostgreSQL 16. All tables have a UUID primary key and `created_at` / `updated_at`. Tables that exist now:

| Table | Purpose |
|-|-|
| `source` | One row per fetch of a document or feed |
| `company` | Company master, keyed by `ticker` |
| `price_daily` | Raw OHLCV per ticker and day, plus `adj_close` |
| `index_daily` | Index levels (DSEX, DSES, DS30). Never constituents. |
| `corporate_action` | Bonus, rights, split, cash dividend |
| `macro_series` | Any dated series: T-bill yields, policy rate, CPI, BDT/USD, Brent, gold |
| `config_version` | Stored copies of each config file version |
| `data_issue` | Failed quality checks awaiting admin review |
| `job_run` | Job run history |
| `audit_log` | Admin actions, overrides, config changes |

All tables for the PRD's features now exist (57 in total). By model file:

| File | Tables |
|-|-|
| `models/market.py` | the ten above |
| `models/user.py` | `app_user`, `user_session`, `password_reset_token` |
| `models/analytics.py` | `financials`, `business_classification`, `shariah_result`, `company_shariah_status`, `shariah_status_change`, `score`, `event`, `event_metric`, `regime_month`, `regime_sector_stat`, `macro_note`, `sukuk_issue`, `islamic_product`, `bank_flag` |
| `models/personal.py` | `household`, `household_member`, `account`, `holding`, `transaction`, `owner_share`, `alt_asset`, `valuation`, `cash_flow`, `document`, `liability`, `expense_category`, `recurring_rule`, `expense`, `zakat_snapshot`, `tax_snapshot`, `net_worth_snapshot`, `target_allocation`, `fire_plan`, `scenario_result`, `goal` |
| `models/platform.py` | `watchlist`, `alert_rule`, `notification`, `push_subscription`, `firm`, `firm_seat`, `api_key`, `api_usage`, `subscription` |

Value sets (statuses, asset types, roles) are in `models/enums.py` and stored as strings. All personal finance data hangs off `household`, so access is one check: is the user a member. Derived tables (`shariah_result`, `score`, `event_metric`, `regime_month`) are written only by analytics jobs.

## Frontend

`frontend/` is an npm workspace:

- `apps/web`: Next.js App Router with the Metronic 9 theme. Routes live under `src/app/[locale]/`, so every URL carries its language (`/bn/...`, `/en/...`). `src/proxy.ts` redirects `/` by the visitor's language, defaulting to Bangla. Pages are server components that fetch through `src/lib/api.ts`; the API address (`API_INTERNAL_URL`) is only known to the server.
- `packages/core`: number, taka and date formatting, and the API response types.
- `packages/i18n`: Bangla and English messages.

The two packages contain no React or Next.js code so the Expo mobile app can import them unchanged.

## Deployment

`docker-compose.yml` at the repo root defines `db`, `migrate`, `api`, `worker` and `web`. CI (`.github/workflows/ci.yml`, D29) has four jobs on every push to `develop` or `main` and every pull request: `backend` (lint, types, unit tests, and migrations applied to PostgreSQL 16 and checked against the models), `frontend` (lint, types, unit tests, production build), `e2e` (Postgres, the API and the built web app with demo data and an administrator, then every Playwright test at desktop and 360 px) and `compose` (`docker compose up --build`, the API health check and a web page).

The static coming-soon page in `coming-soon/` is published separately by Netlify (`netlify.toml`) until the web app replaces it.

## Accounts, sessions and roles

```
Browser --form post--> Next.js server --Bearer token--> FastAPI --> app_user, user_session
        <--httpOnly cookie--
```

- Sign-in returns an opaque token. The Next.js server stores it in the httpOnly `dn_session` cookie and sends it to the API as a Bearer header. The database holds only the token's SHA-256 hash. The mobile app will keep the same token in secure storage.
- `frontend/apps/web/src/lib/session.ts` reads the cookie, loads the current user once per request, and guards pages with `requireUser` and `requirePermission`. Forms post to server actions in `src/app/actions/`.
- The API answers refusals with a stable code (`{"detail": "EMAIL_TAKEN"}`); the web app translates it under the `errors` messages.
- Each user has one role. `backend/app/core/permissions.py` maps roles to permissions, and routes depend on `require_permission(...)`. `GET /me` returns the user's permissions so the UI can hide what the user may not do; the API still enforces every check.
- Role changes, deactivation, consent changes, password changes and deletions are written to `audit_log`.

Tables: `app_user` (email, password hash, name, locale, role, active flag, consents, lock state), `user_session` (token hash, client, expiry, revoked time), `password_reset_token`.

## Design system

The UI is Metronic 9, Layout 9. Theme tokens are in `apps/web/src/app/globals.css`; copied Metronic components are in `src/components/ui`; the header, menu bar, toolbar and footer are in `src/components/layout`. Pages for visitors and signed-in users share the `(site)` layout; sign-in pages use the `(auth)` layout (a centred card).

## Not built yet

Household tables, payments, email delivery and push, object storage, the data review screens and the generated API client. See [ROADMAP.md](ROADMAP.md).
