# Decisions

Short record of choices that are not obvious from the code. Add a new entry at the bottom; do not rewrite old ones. If a decision is reversed, add a new entry that says so.

## D1. Next.js instead of Nuxt for the web app (2026-11-14)

The PRD first named Nuxt (Vue). A native mobile app is planned (F11). Next.js with React lets the mobile app be built in Expo (React Native) and reuse the TypeScript packages: formatting, messages, API client. PRD section 11 was revised to match.

## D2. Python and FastAPI own every calculation (2026-11-14)

Shariah screening, regressions, XIRR, Zakat and FIRE are computed on the backend only. Clients display results. This keeps one implementation for web and mobile and keeps every number traceable to a source and a timestamp.

## D3. npm workspaces, no pnpm or Turborepo (2026-11-14)

The frontend has one app and two small packages. npm workspaces need no extra install on the dev machine. Revisit when the mobile app is added and build caching starts to matter.

## D4. next-intl for translations (2026-11-14)

next-intl fits the App Router and server components. Its core, `use-intl`, runs in React Native, so the mobile app can load the same message files from `frontend/packages/i18n`.

## D5. Synchronous SQLAlchemy with psycopg 3 (2026-11-14)

Request handlers read precomputed rows; heavy work runs in the worker. Sync sessions are simpler to write and test, and FastAPI runs sync handlers in a thread pool. Move specific endpoints to async only if measurements show a need.

## D6. Portable column types, Postgres in production (2026-11-14)

Models use SQLAlchemy `Uuid`, and `JSON` with a `JSONB` variant on Postgres. Unit tests therefore run on in-memory SQLite on a machine without Postgres. CI also runs the migrations against Postgres 16. Anything Postgres-only must be covered by a CI test.

## D7. Web sessions by cookie, mobile by bearer token (2026-11-14)

The PRD allowed "session cookies or JWT". Web uses httpOnly secure cookies with CSRF protection. The same server-side session table will issue opaque bearer tokens for the mobile app. No JWT: sessions must be revocable for account deletion (FR23.4).

## D8. The coming-soon page stays live from `coming-soon/` (2026-11-14)

The static page moved out of the repo root. `netlify.toml` publishes that folder so merging to `main` does not change the public site. Remove it when the web app replaces the page.

## D9. Docker Compose file at the repo root (2026-11-14)

The PRD put it in `infra/`. It is at the root so `docker compose up` works with no flags, as the M0 definition of done states.

## D10. The API issues opaque tokens; the web server holds the cookie (2026-11-14)

Refines D7. FastAPI only accepts `Authorization: Bearer <token>`. The Next.js server calls the API, keeps the token in an httpOnly `dn_session` cookie on its own origin, and forwards it. The browser never calls the API or sees the token. Web and mobile therefore use one auth mechanism, the API needs no cookie or CSRF handling, and form posts are protected by the origin check built into Next.js server actions. Only the SHA-256 hash of each token is stored.

## D11. Metronic 9 Layout 9 is the design for the whole app (2026-11-14)

The owner holds a ThemeForest licence for Metronic and chose its Layout 9 (fixed header with search, menu bar, centred content). Only the pieces in use were copied from the Tailwind/Next.js starter kit into `frontend/apps/web/src/components/ui` and adapted in `components/layout`; the theme download stays outside the repo. Consequences:

- The repo must stay private: the licence does not allow redistributing theme source.
- The licence file in the download says a SaaS that charges end users needs the Extended licence. Confirm before Pro or Firm plans go on sale (with Q4).
- The primary colour is the analysisACE sky blue instead of Metronic's default.
- Metronic ships Recharts and ApexCharts; charts will use Recharts through the theme's chart component, replacing the earlier ECharts plan.

## D12. Three fixed platform roles, permissions checked in code (2026-11-14)

Roles are `USER`, `ANALYST` and `ADMIN`, defined with their permissions in `backend/app/core/permissions.py`. Routes check a permission, never a role name. Roles are not editable in the UI: with three roles a role editor adds risk and no value. Household roles (FR24.2) and firm roles (FR9.3) are separate concepts and will be added with those features.

## D13. Account table is `app_user`; reset is two endpoints (2026-11-14)

`user` is a reserved word in PostgreSQL, so the table in PRD section 9 is named `app_user`. PRD section 10 lists one `POST /auth/reset`; it is built as `/auth/password-reset/request` and `/auth/password-reset/confirm`. Email verification at sign-up is not built yet because no email provider is chosen; until one is, emails are written to the API log.

## D14. Brand: logo, colours and fonts from the owner's logo artifact (2026-11-14)

The brand comes from the owner's "analysisACE Logo" design artifact: a navy "A" mark with three bars, wordmark "analysis" + "ACE" in Space Grotesk (renamed from Datanytics).

- Colours: navy `#0B1F3A`, bright teal `#2DD4BF`, deep teal `#0F766E` (the teal used for text and buttons on light backgrounds, 5.5:1 against white). They are theme tokens in `globals.css` (`brand-navy`, `brand-teal`, `brand-teal-deep`). Light mode uses navy text with a deep-teal primary; dark mode uses a navy background with a bright-teal primary.
- The logo is `components/brand/logo.tsx` (inline SVG that follows the theme). Favicon and app icons are generated by `npm run brand:assets` (`scripts/build-brand-assets.mjs`) into `src/app/icon.svg`, `apple-icon.png`, `favicon.ico` and `public/icon-512.png`. If the logo changes, update the artifact, the component and the script together.
- Space Grotesk is used for the wordmark and the home headline only. Body text stays Inter, with Noto Sans Bengali for Bangla.
- This replaces the earlier sky-blue primary colour noted in D11. The static page in `coming-soon/` still shows the old logo.

## D15. Demo data is synthetic and uses fictional companies (2026-11-15)

`scripts/seed_demo.py` fills every feature with data, but none of it is real. Companies are invented (tickers start with `DM`), prices are a seeded random walk, and macro series only follow a plausible shape. Every row points at a `source` named "Demo data (synthetic, not real market data)", which the app shows wherever the data appears. Reasons: the hard rule that every number is traceable, and the risk of attaching an invented price or Shariah verdict to a real company. Index codes (DSEX, DSES, DS30) are real names with synthetic levels.

Only base data is seeded. Screening results, scores, event metrics, regimes, net worth history, Zakat snapshots and FIRE plans are produced by the analytics code, so those numbers are always computed. The older `scripts/seed_dev.py` (16 real company names, no prices) was removed in favour of this.

## D16. Tables added beyond PRD section 9 (2026-11-15)

- `company_shariah_status` and `shariah_status_change`: the status shown now and its history (FR1.4), kept apart from per-method `shariah_result` rows so lists can filter by status and alerts have a change record.
- `regime_sector_stat` (FR8.2), `macro_note` (F4), `liability` and `net_worth_snapshot` (FR14.4), `target_allocation` (FR16.2), `push_subscription` (FR7.1).
- `owner_share` and `valuation` point at holdings, alternative assets or liabilities through `asset_kind` + `asset_id` with no foreign key. `services/household_data.py` removes them when a household is deleted.
- Unit tests run SQLite with foreign keys enforced, after a row-ordering bug passed on SQLite and failed on PostgreSQL.
