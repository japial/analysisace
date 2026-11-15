# Roadmap and status

Milestones are defined in [PRD.md](PRD.md) section 14 and are built in order. Update this file when an item is finished. Last updated: 2026-11-14.

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
- [ ] Job that writes `adj_close` from `corporate_action` using `analytics/adjustment.py`
- [ ] Index ingestion (DSEX, DSES, DS30 levels) and `GET /indices/{code}/series`
- [ ] Macro series ingestion and `GET /macro/series/{code}`; manual admin entry for gold and silver price (Q9)
- [ ] Live adapters: DSE day-end archive, DSE corporate actions, DSE company master, Bangladesh Bank T-bill auctions. **Blocked on Q5** (may DSE day-end data be stored and shown commercially) and on reading each site's terms of use
- [ ] Choose and convert a public EOD dataset for the 5-year backfill
- [ ] Wire the quality checks that span days (missing days, unexplained moves, staleness) into a daily job
- [ ] Admin review queue for `data_issue` (needs authentication, so it may move into M2)
- [ ] Alert on failed jobs

## Build phases (owner's plan, 2026-11-15)

1. **Database and seed data for every feature: done.** 57 tables, three migrations, demo seed, export and deletion cover the new personal tables.
2. **API for every feature: next.** Analytics code first (screening, rate sensitivity, event metrics, regime, XIRR and returns, Zakat, FIRE), then the routes.
3. **Frontend for those APIs: after phase 2.**

In the table below, "Not built" now means: tables and demo data exist, but there is no calculation, API or screen yet.

## Status of every PRD feature

Last updated 2026-11-14. "Blocked" means a decision or input from the owner is needed, not just work. Release names are from PRD section 4.

| ID | Feature | Release | Status | What is missing |
|-|-|-|-|-|
| F1 | Shariah screen per company | MVP | Not built | Financial statements data (PDF extraction and review screen), screening engine, advisor sign-off (Q1) |
| F2 | Shariah list and DSES vs DSEX tracker | MVP | Not built | Price and index data (Q5), basket calculation, chart |
| F3 | Rate sensitivity score | MVP | Not built | Prices, corporate actions and T-bill yields loaded; regression job |
| F4 | Weekly macro note (bn, en) | MVP | Not built | Macro data feeds; admin publish screen |
| F5 | Shock playbook | R2 | Not built | Event library, prices |
| F6 | Portfolio check | R2 | Not built | F14 holdings and F1 screening |
| F7 | Alerts (status, regime, shock) | R2 | Not built | Email provider, web push, F1 |
| F8 | Macro regime dashboard | R3 | Not built | Macro data |
| F9 | Firm features (white-label, CSV, API, seats) | R3 | Not built | Firm accounts, PDF reports, API keys; legal check (Q4) |
| F10 | Ownership change layer | Later | Not built | Data source |
| F11 | Native mobile app | Later | Not built | Web releases first |
| F12 | Daily cost records | R2 | Not built | None. Can start now |
| F13 | Tax and Zakat snapshot | R2 | Not built | Needs F14, F25, F26 inputs; advisor review of rules (Q2). Ramadan 2027 deadline |
| F14 | Portfolio aggregation | R2 | Not built | Sample broker statements for CSV import; prices for valuation |
| F15 | Performance tracking | R3 | Not built | F14, prices |
| F16 | Asset allocation and drift | R3 | Not built | F14 |
| F17 | FIRE calculator | R3 | Not built | F12, F14. The calculation itself needs no outside data |
| F18 | Scenario planning | R3+ | Not built | F17, F5 |
| F19 | Goal tracking | R3 | Not built | None |
| F20 | Personal alerts and monthly report | R3 | Not built | Email provider |
| F21 | Community benchmarking | Later | Not built | 50-user minimum, consent already exists |
| F22 | News sentiment | Later | Not built | Data source |
| F23 | Data privacy controls | Every release | Partly built | Done: consents, export, deletion, encryption of passwords and tokens. Missing: field-level encryption of account numbers and documents (needs those tables), breach-notification and retention notices (legal text), confirmation of the Personal Data Protection Ordinance status (Q3) |
| F24 | Multi-owner household records | R3+ | Not built | None. Household tables are also needed by F12 to F14 |
| F25 | Alternative investments | R2 basic, R3 full | Not built | Object storage for documents |
| F26 | Sukuk and Islamic bank investments | R2 / R3 | Not built | Product catalogue content, bank flag content |

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
- [ ] Audit log viewer for admins (permission `AUDIT_VIEW` exists; no screen yet)

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
