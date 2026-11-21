# Roadmap and status

Milestones are defined in [PRD.md](PRD.md) section 14 and are built in order. Update this file when an item is finished. Last updated: 2026-11-21.

## M0 Project setup

Definition of done: `docker compose up` runs API, worker, DB and frontend; CI green.

- [x] Repo restructured: `backend/`, `frontend/`, `config/`, `docs/`, `coming-soon/`
- [x] `CLAUDE.md` (root, backend, frontend), architecture, decisions
- [x] Backend scaffold: FastAPI app, settings, database session, Alembic, worker process
- [x] Base config files in `config/` with a versioned loader
- [x] Frontend scaffold: Next.js app, shared `core` and `i18n` packages, Bangla and English
- [x] Lint, type check and tests pass locally for backend and frontend
- [x] Dockerfiles, `docker-compose.yml`, GitHub Actions workflow written
- [ ] **Confirm `docker compose up` and CI pass.** Neither could be run on the dev machine (no Docker). Push the branch and check the first CI run.

## M1 Data foundation

Definition of done: daily job runs unattended for 10 trading days; quality checks pass; 5+ years backfilled.

Done:

- [x] Tables and first migration: `source`, `company`, `price_daily`, `index_daily`, `corporate_action`, `macro_series`, `config_version`, `data_issue`, `job_run`, `audit_log`
- [x] Trading calendar (Sunday to Thursday, holidays and special days from config)
- [x] Price back-adjustment for bonus, rights and splits, with worked examples and a property test
- [x] Data quality checks: missing trading days, duplicates, null required fields, moves over the limit with no corporate action, stale source
- [x] Adapter interface for end-of-day prices; CSV adapter for backfill files
- [x] Price ingestion service (idempotent reload, quality issues stored for review)
- [x] Config version registry
- [x] Public API: `GET /health`, `GET /meta`, `GET /companies`, `GET /companies/{ticker}`
- [x] Web pages: home, company list with search, company detail

Next, in this order:

- [ ] Fill `holidays` in `config/trading_calendar.yaml` from DSE holiday notices (2020 onward)
- [ ] Confirm the floor-price dates in `config/excluded_periods.yaml` against DSE and BSEC orders
- [x] Job that writes `adj_close` from `corporate_action` (`adjusted_prices`); admin entry of corporate actions rewrites a ticker's adjusted closes at once
- [x] `GET /indices/{code}/series` and `GET /macro/series/{code}`; admin CSV load for index and macro series (backfill path until live adapters exist)
- [x] Manual admin entry for gold and silver price (Q9), with a check against typing errors
- [ ] Live adapters: DSE day-end archive, DSE corporate actions, DSE company master, Bangladesh Bank T-bill auctions. **Blocked on Q5** (may DSE day-end data be stored and shown commercially) and on reading each site's terms of use
- [ ] Choose and convert a public EOD dataset for the 5-year backfill
- [x] Quality checks that span days run daily (`data_quality`); open issues are not repeated
- [x] Admin review queue for `data_issue` (`/admin/data`)
- [ ] Alert on failed jobs. Failed runs show on `/admin/audit` (jobs table); an email alert needs the email provider

## Build phases (owner's plan, 2026-11-15)

1. **Database and seed data for every feature: done.** 57 tables, three migrations, demo seed, export and deletion cover the new personal tables.
2. **API for every feature: personal finance done (2026-11-17), market layer done (2026-11-21).** Screening, basket, rate sensitivity, event metrics, regime, macro notes, market check and market alerts run on stored data (docs/DECISIONS.md, D17). Live data adapters still wait on Q5.
3. **Frontend for those APIs: personal finance done (2026-11-17), market layer done (2026-11-21).** Public pages `/shariah`, `/rates`, `/events`, `/macro`, `/regime`, the company page's screen, scores and event table, `/personal/market-check`, and admin screens under `/admin` (data, Shariah, events, notes, audit), in Bangla and English, with browser tests (`e2e/market.spec.ts`).
   Personal finance: "My money" (`/personal`, menu entry for signed-in users) has a page for each of F12 to F21 and F24 to F26, in Bangla and English, with browser tests at desktop and 360 px (`e2e/personal.spec.ts`).

In the table below, "Not built" now means: tables and demo data exist, but there is no calculation, API or screen yet. "Built" means API and screens exist; what is listed is still open.

## Status of every PRD feature

Last updated 2026-11-21. "Blocked" means a decision or input from the owner is needed, not just work. Release names are from PRD section 4.

| ID | Feature | Release | Status | What is missing |
|-|-|-|-|-|
| F1 | Shariah screen per company | MVP | Built | Advisor sign-off of thresholds (Q1); automatic PDF extraction (figures are entered and reviewed by hand); real financial statements |
| F2 | Shariah list and DSES vs DSEX tracker | MVP | Built | Real price and index data (Q5) |
| F3 | Rate sensitivity score | MVP | Built | Real prices, corporate actions and T-bill auctions (Q5 and a Bangladesh Bank adapter); confirmed floor-price dates |
| F4 | Weekly macro note (bn, en) | MVP | Built | Live macro data feeds (Bangladesh Bank, BBS, Brent) |
| F5 | Shock playbook | R2 | Built | Curate real events and Bangladesh Bank policy-rate changes; confirm the LNG fire date |
| F6 | Portfolio check | R2 | Built | — |
| F7 | Alerts (status, regime, shock) | R2 | Partly built | In-app alerts and watchlist work. Missing: email provider, web push |
| F8 | Macro regime dashboard | R3 | Built | Owner to confirm the inflation bands and choose a liquidity series (FR8.1) |
| F9 | Firm features (white-label, CSV, API, seats) | R3 | Not built | Firm accounts, PDF reports, API keys; legal check (Q4) |
| F10 | Ownership change layer | Later | Not built | Data source |
| F11 | Native mobile app | Later | Not built | Web releases first |
| F12 | Daily cost records | R2 | Built | — |
| F13 | Tax and Zakat snapshot | R2 | Built | Advisor review of rules (Q2). PDF statements in Bangla and English done (2026-11-21) |
| F14 | Portfolio aggregation | R2 | Built | Check broker CSV aliases against real statements from two brokers |
| F15 | Performance tracking | R3 | Built | — |
| F16 | Asset allocation and drift | R3 | Built | — |
| F17 | FIRE calculator | R3 | Built | — |
| F18 | Scenario planning | R3+ | Built | — |
| F19 | Goal tracking | R3 | Built | — |
| F20 | Personal alerts and monthly report | R3 | Built | Email provider; web push (alerts show in the app and log emails until then) |
| F21 | Community benchmarking | Later | Built | Needs 50 opted-in users per age band before a group shows |
| F22 | News sentiment | Later | Not built | Data source |
| F23 | Data privacy controls | Every release | Partly built | Done: consents, export, deletion, encryption of passwords and tokens. Missing: field-level encryption of account numbers and documents (needs those tables), breach-notification and retention notices (legal text), confirmation of the Personal Data Protection Ordinance status (Q3) |
| F24 | Multi-owner household records | R3+ | Built | — |
| F25 | Alternative investments | R2 basic, R3 full | Built | S3 storage (documents are encrypted on local disk for now) |
| F26 | Sukuk and Islamic bank investments | R2 / R3 | Built | Real product catalogue and bank flag content (admin screen `/admin/bank-flags` done 2026-11-21) |

Also built, not a numbered feature: accounts, roles and user management (see below), the data foundation tables, the trading calendar, price adjustment and quality checks.

### Suggested order

1. **Personal finance layer first** (household tables, F12, F14 manual entry, F25, F26, F13 Zakat, F17 FIRE, F19 goals). Nothing here waits on a data licence, and Zakat must ship before Ramadan 2027 (about early February 2027).
2. **Data adapters** as soon as Q5 is answered, then F2, F3, F5, F4, F8.
3. **Shariah screening** (F1) once the advisor signs off the method (Q1) and financial statements are being extracted.
4. **Alerts, firm features and payments** once the email provider, the Extended Metronic licence and the BSEC check (Q4) are settled.

## Accounts and roles (built ahead of M2 at the owner's request)

Covers the "Auth, consents, account deletion and export" item of M2 and the role checks every admin feature needs.

- [x] Tables and migration: `app_user`, `user_session`, `password_reset_token`
- [x] Sign-up with explicit consent, sign-in, sign-out, password reset, password change
- [x] Lock after repeated wrong passwords; sessions revocable; only token hashes stored
- [x] Profile, privacy choices (consents with audit trail), data export, account deletion (FR23.1, FR23.2, FR23.4)
- [x] Roles `USER`, `ANALYST`, `ADMIN` with permissions; admin screens for users and roles; audit log entries
- [x] Web app redesigned on Metronic Layout 9 (header, menu bar, auth pages, cards, tables, light and dark)
- [x] Browser tests (Playwright) for the account flows at desktop and 360 px width
- [ ] Choose a transactional email provider. Until then reset emails are only written to the API log
- [ ] Email verification at sign-up (needs the provider)
- [ ] Rate limit sign-up and reset requests per IP (needs Redis or a proxy rule)
- [ ] Run the Playwright tests in CI (needs the stack started inside the workflow)
- [x] Audit log viewer for admins (`/admin/audit`, with recent job runs)

## M2 MVP: F1, F2, F3, F4, F23 basics

Not started, apart from the accounts work above. Needs the Shariah advisor's sign-off on `config/shariah.yaml` (Q1) and a legal check on the free pages.

## M3 Release 2 (before Ramadan 2027, about early February 2027)

Not started.

## M4 Release 3

Not started.

## Open items that need the owner

| Item | Why it matters |
|-|-|
| Q5: DSE data licensing | Decides which price adapter is written first |
| Q1: Shariah advisor and method | Thresholds in `config/shariah.yaml` are provisional |
| Bangla text review | `frontend/packages/i18n/messages/bn.json` was written without a native reviewer |
| Netlify settings | `netlify.toml` now publishes `coming-soon/`. Check the site still deploys after merging to `main` |
| Metronic licence type | An Extended licence is needed before charging users (see DECISIONS D11) |
| Email provider | Password reset emails are not delivered until one is chosen |
| Coming-soon page wording | It promises "Predictive AI" forecasts, which conflicts with the no-signals rule |
