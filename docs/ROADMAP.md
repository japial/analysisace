# Roadmap and status

Milestones are defined in [PRD.md](PRD.md) section 14 and are built in order. Update this file when an item is finished. Last updated: 2026-11-23.

**Product focus (2026-11-23, D19):** analysisACE helps a household grow its ACE: Assets, Capital, Earnings. Stock analysis is one kind of capital, an optional tool layer, not the headline. Features below are grouped by pillar in the status table.

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
- [x] Alert on failed jobs: emails `OPS_ALERT_EMAILS` (D24, 2026-11-24). Failed runs also show on `/admin/audit`

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
| F7 | Alerts (status, regime, shock) | R2 | Built | In-app, email (D24) and browser push (D26). Owner: choose the email provider and generate push keys |
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
| F20 | Personal alerts and monthly report | R3 | Built | Email provider choice; push keys (D24, D26) |
| F21 | Community benchmarking | Later | Built | Needs 50 opted-in users per age band before a group shows |
| F22 | News sentiment | Later | Not built | Data source |
| F23 | Data privacy controls | Every release | Partly built | Done: consents, export, deletion, encryption of passwords and tokens. Account numbers and documents are encrypted (FR23.3). Missing: breach-notification and retention notices (legal text), confirmation of the Personal Data Protection Ordinance status (Q3) |
| F24 | Multi-owner household records | R3+ | Built | — |
| F25 | Alternative investments | R2 basic, R3 full | Built | S3 storage (documents are encrypted on local disk for now) |
| F26 | Sukuk and Islamic bank investments | R2 / R3 | Built | Real product catalogue and bank flag content (admin screen `/admin/bank-flags` done 2026-11-21) |
| F27 | Income records and savings | R2 | Built | Tax line mapping (`income.tax_lines`) is provisional until the tax adviser review (Q2) |

Also built, not a numbered feature: accounts, roles and user management (see below), the data foundation tables, the trading calendar, price adjustment and quality checks.

### ACE pillars

| Pillar | Features | State |
|-|-|-|
| **Assets** | F14, F24, F25, F26, F13 (Zakat, wealth statement) | Built. Open: advisor review of Zakat rules (Q2), broker CSV aliases, S3 storage, product catalogue content |
| **Capital** | F15 to F19, F6, and the stock tools F1 to F5, F8 | Personal capital features built. Stock tools built on demo data; real data waits on Q5 |
| **Earnings** | F12, F27, income and tax parts of F13, F20 | Built. Open: email provider for reminders and the monthly report |
| Platform | F7, F9, F11, F21, F23 | F9 and F11 not built |

### Suggested order

1. **Assets and Earnings first.** Nothing here waits on a data licence, and Zakat must ship before Ramadan 2027 (about early February 2027). Start the advisor review of the Zakat rules (Q2) now. Polish the first-run experience: guided set-up of the first household (done 2026-11-24, D22), an ACE summary on the My money overview (done), and import helpers (income CSV done 2026-11-24; import errors now say why a row was skipped).
2. **Capital plans:** FIRE, goals, scenarios and drift are built; finish tuning with real households. Add an ACE trend (how net worth, capital share and savings changed month by month): done 2026-11-24 (D23).
3. **Email provider and reminders**, so dues, maturities, Zakat dates and the monthly report reach people outside the app. Sending is built (D24) and sign-up verifies the address (D25); the owner picks the provider and verifies the domain. Browser push built (D26). Still open: HTML email templates, bounce handling.
4. **Stock tools and data adapters** as soon as Q5 is answered (F2, F3, F5, F4, F8), and Shariah screening (F1) once the advisor signs off the method (Q1).
5. **Firm features and payments** (F9) once the Extended Metronic licence and the BSEC check (Q4) are settled.

### Positioning work

- [x] Landing page, hero, menu and message files rewritten around ACE (2026-11-23)
- [x] PRD overview, goals, personas and ACE map updated; decision D19
- [x] Coming-soon page rewritten
- [x] Landing page and coming-soon page refocused on FIRE, with ACE as the levers (D21, 2026-11-23)
- [x] My money overview leads with FIRE progress (`GET /fire/progress`): projected FIRE age from the newest plan, or an estimated FIRE number from costs, with savings rate. A partial year of costs is now annualised (average month x 12) for the estimate and the FIRE form (2026-11-23)
- [x] My money overview shows an ACE card (net worth, capital at work, average monthly cost) from `GET /households/{id}/ace/summary`, and the section menu is grouped Assets, Capital, Earnings, Plans (2026-11-23)
- [x] Income records and savings (F27, 2026-11-23): income entries and recurring income, monthly savings and savings rate, ACE card and FIRE default use them. Linked (2026-11-23): tax statement takes salary and other income from the records (FR27.5), monthly report shows income and savings, "saved each month" goal type, FIRE default, community comparison through the FIRE plan. CSV import and export of income done (FR27.7, 2026-11-24). The in-app monthly report notice shows income and savings when recorded (2026-11-24)
- [x] Guided set-up (D22, 2026-11-24): "Getting started" checklist on the overview and a one-form quick start for birth year, monthly income, typical costs and savings held
- [x] ACE trend on the overview (D23, 2026-11-24): net worth and capital at work by month, change over the period, and monthly income, costs, savings and savings rate. Snapshots now keep capital at work (migration 0005)
- [x] A holding with a DSE ticker shows "About this company" (Shariah status, rate sensitivity, link to the company page), so shares lead to the stock tools (2026-11-24)
- [ ] Bangla text review of the new landing copy (with the existing Bangla review item)

## Accounts and roles (built ahead of M2 at the owner's request)

Covers the "Auth, consents, account deletion and export" item of M2 and the role checks every admin feature needs.

- [x] Tables and migration: `app_user`, `user_session`, `password_reset_token`
- [x] Sign-up with explicit consent, sign-in, sign-out, password reset, password change
- [x] Lock after repeated wrong passwords; sessions revocable; only token hashes stored
- [x] Profile, privacy choices (consents with audit trail), data export, account deletion (FR23.1, FR23.2, FR23.4)
- [x] Roles `USER`, `ANALYST`, `ADMIN` with permissions; admin screens for users and roles; audit log entries
- [x] Web app redesigned on Metronic Layout 9 (header, menu bar, auth pages, cards, tables, light and dark)
- [x] Browser tests (Playwright) for the account flows at desktop and 360 px width
- [x] Email sending over SMTP, provider chosen by settings (D24, 2026-11-24)
- [x] Provider: Gmail SMTP (D27, 2026-11-26)
- [ ] Owner: on the production server set `EMAIL_BACKEND=smtp`, `SMTP_USERNAME` and `SMTP_PASSWORD` (Gmail app password). Until then mail is only written to the log. Past about 500 emails a day (the monthly report to every user) move to Google Workspace or a transactional provider
- [x] Email verification at sign-up (D25, 2026-11-24): soft, alert and report emails wait for a confirmed address
- [x] Rate limits on sign-up, sign-in, password reset and verification emails (D28, 2026-11-26). Production: the reverse proxy in front of the web app must set `X-Forwarded-For`
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
