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

## D17. Market analytics run on stored data only, in one nightly pipeline (2026-11-21)

F1, F2, F3, F5, F6 and F8 are computed by `services/market_pipeline.py` (worker job `market_analytics`, also runnable by an admin) from rows already in the database: adjusted closes, index levels, macro series and reviewed financials. No outside service is called, so the features work on demo data now and on real data once the adapters exist (Q5). Choices made along the way:

- **Screening market cap** is the mean of daily close × shares outstanding over the method's trailing window ending on the period end, so a result can be reproduced from stored prices. A stored result is updated in place only when its inputs change under the same config version (a reclassification or corrected figures); shown-status changes are always kept in `shariah_status_change`.
- **Only reviewed financials are screened** (`reviewed_at` set). Reviewing figures re-screens that company at once (FR1.4).
- **Rate sensitivity** uses weekly DSE weeks keyed by their Sunday. A week is dropped if it or the week before touches a floor-price period, or if either week had no trade. Standard errors are Newey-West (Bartlett, default lag `floor(4(n/100)^(2/9))`) with an n/(n−k) factor. Sector scores use an equal-weight sector index.
- **The Shariah basket** (FR2.2) uses the current COMPLIANT set at every monthly rebalance, as the PRD acceptance criterion says. Its history therefore shows how today's list would have moved, and the page says so. Levels are stored in `index_daily` under `AACE_SHARIAH_EW` with a `source` row naming the computation.
- **Event metrics** are also computed for the DSEX (`subject_type = INDEX`), so an event page can show the market's move.
- **Regime inflation bands** are not in the PRD. Provisional bands (under 6%, 6 to 9%, 9% and over) are in `config/regime.yaml` with a TODO for the owner; the liquidity trend is off until a series and rule are chosen.
- **Market alerts (F7)** are in-app only until an email provider and web push exist. Status changes reach holders and watchers; regime and shock alerts reach only users who turned them on.
- **Gold and silver prices** are entered by an admin (Q9 default), with a check that refuses a move of more than 15% from the previous value. Index and macro series can also be loaded from CSV for backfills.

## D18. PDF statements with fpdf2 and HarfBuzz shaping (2026-11-21)

Zakat and tax statements (F13) are made as PDFs by the API (`services/statements.py`), in the language the person asks for. fpdf2 is used with `uharfbuzz` because Bangla needs text shaping for joined letters; ReportLab draws Bangla wrongly, and WeasyPrint needs GTK on Windows. Fonts are Noto Sans and Noto Sans Bengali, kept in `backend/app/assets/fonts` under the SIL Open Font License (OFL.txt beside them).

A PDF repeats the stored snapshot; nothing is recalculated. Each page carries the disclaimer, and the end of the statement gives the computation time and the sources of the market prices valid on the snapshot date. Enum labels are copied from the web message files into `services/statement_labels.py`, and a test fails if the two copies differ. The browser "print" button was replaced by a "Download PDF" button. The same document class can produce the F9 white-label weekly report later.

## D19. The product is organised around ACE, with stocks as one kind of capital (2026-11-23)

The owner clarified that analysisACE is mainly a personal finance app whose goal is to improve a household's ACE (Assets, Capital, Earnings). Stock market analysis is one portfolio type among others, not the headline. Consequences:

- **Pillars.** Assets = what is owned and owed (F14, F24, F25, F26, Zakat and wealth statement). Capital = money put to work and the plans it funds (F6, F15 to F19, and the stock tools F1 to F5, F8). Earnings = income, costs, savings, tax and reminders (F12, F20, income and tax parts of F13). The map is in PRD section 4.
- **Landing page.** Leads with ACE and a sample household, then the three pillars, the questions households ask, and only then the stock tools ("Holding DSE shares? Understand them better"). The Shariah list is no longer the main call to action.
- **Menu.** "My money" is a main menu item for everyone (signed-out visitors are sent to sign in) and comes before the stock tools. The "Markets" group is renamed "Stock tools" and sits after My money.
- **Routes are unchanged.** `/shariah`, `/rates`, `/events`, `/macro`, `/regime` and `/companies` keep their paths because notifications and tests link to them. They are public pages and remain the free way in for people who hold shares.
- **Build order.** Assets and Earnings come first, then Capital plans, then the stock tools as data licensing (Q5) allows. Nothing already built is removed.
- **Coming-soon page.** Rewritten to the same positioning, without the "Predictive AI" claim that conflicted with the no-signals rule.
- **Name of the second pillar.** "Capital" (singular), meaning invested money. In Bangla it is মূলধন.

## D20. Income records feed the tax statement, never Zakat (2026-11-23)

Income records (F27) are linked wherever a figure was typed by hand or guessed before:

- **Tax statement (FR27.5).** Salary and other income default to the member's records for the tax year. Typing a value overrides the records, and the statement stores which was used (`income_basis`). Rent, profit and dividends are not taken from income records, because the statement already works them out from holdings and asset cash flows; counting both would count twice. Remittance is treated as exempt. Records with no member are not counted for anyone. The mapping lives in `config/personal.yaml` and is provisional (Q2).
- **FIRE (F17)** starts from the 12-month average saving, floored at zero. **Community comparison (F21)** reads the FIRE plan, so it improves through that default and is not changed directly.
- **Goals (F19)** gain `MONTHLY_SAVINGS`, measured against the 12-month average. **Monthly report (F20)** gains last month's income and savings in the email.
- **Zakat is not linked.** Zakat is due on wealth held on the Zakat date. Income is already counted once it sits in a bank or cash balance, so adding it from records would count it twice.
- **Message groups.** `personal.enum.incomeKind` stays the tax statement's line names (shared with the PDF labels); the recorded kinds use `personal.enum.incomeType`.

## D21. The landing page leads with FIRE; ACE are the levers (2026-11-23)

The owner asked for the landing page to focus on FIRE-oriented personal finance. The hero promises a FIRE date ("Find the year work becomes optional") and shows a sample FIRE plan. The page then explains the FIRE number (a year of costs × 25 at a 4% withdrawal rate), the savings rate and the FIRE date; shows why the savings rate matters more than returns; presents Assets, Capital and Earnings as levers on the FIRE date; and lists what a plan must handle in Bangladesh. Each Bangladesh point is backed by a built feature: BBS CPI inflation, returns from the household's own sukuk and deposits, family support as a cost, land and home left out of the investable base, Zakat, and the five stress tests.

- **Savings-rate table.** Fixed illustrative text, not data: years from zero to 25× costs at a 5% real return, n = ln(1 + 25(1 − s) × 0.05 / s) / ln 1.05, rounded. It states its assumptions and says it is not a forecast. Figures in the hero illustration are fictional and agree with each other.
- **Wording.** FIRE ages are always "projected" or "could"; the FAQ says a FIRE age is not a promise. This keeps the no-advice rule.
- **Main call to action.** Goes to the FIRE plan for signed-in visitors, and to sign-up ("Start your FIRE plan") otherwise.

## D22. Guided set-up: a checklist and one quick-start form (2026-11-24)

A new household had nothing to start from, and every FIRE figure needs income and costs. Set-up has two parts:

- **Checklist** on the My money overview: birth year, income, costs, what you hold, a FIRE plan. Each step's state is read from the household's records (`GET /setup/status`), so it stays true when data is added on the usual pages. It disappears when all five are done.
- **Quick start** (`/personal/setup`, `POST /setup/quick-start`): one form, one transaction. It calls the same services as the other pages, so what it makes is ordinary data that can be changed or deleted. Income and fixed costs become monthly rules from the 1st of the current month, so this month has entries and a savings rate shows at once. Day-to-day costs are entered once, today, as this month's estimate, because they vary and a rule would invent future spending. Savings become one account and one holding per kind, named in the person's language.
- **Configuration.** Which categories are fixed or day-to-day, the savings kinds and the note on created records live in `config/personal.yaml` under `setup`.
- **Left out on purpose.** Shares (better from a broker statement, which carries tickers and costs) and gold and land (they need weights or valuations). The form points to those pages.
- **Running it twice adds again.** It does not try to merge; each section says when records already exist.

## D23. ACE trend from stored snapshots and records (2026-11-24)

The overview's net-worth chart becomes "Your ACE over time": net worth and capital at work as two lines, the change over the period, and income, costs, savings and savings rate for recent months (`GET /ace/trend`, 3 to 36 months, 12 by default).

- **Capital at work is stored, not rebuilt.** Valuing the portfolio at twelve past month-ends on every request would break the API's speed budget, so the daily snapshot now keeps `capital` (migration 0005) next to net worth, using the same measure as the ACE card. Snapshots stored before this have no capital; their months show a gap, not zero.
- **Each month uses its last snapshot.** A month with no snapshot shows no net worth. Income, costs and savings come from the records, as on the Income page.
- **No income means unknown, not zero.** With no income records anywhere in the period, income and savings are left empty, so a household that only records costs is not shown a loss every month. Once any month has income, a month without it is shown as the shortfall it is.
- **Demo data** stores month-end snapshots for the last 12 months so the demo has a trend.

## D24. Email goes out over SMTP; the provider is a setting (2026-11-24)

No transactional email provider has been chosen. Rather than wait, sending is built against SMTP, which every common provider offers (Amazon SES, Postmark, SendGrid, Mailgun, Resend, Brevo). Choosing one is a matter of `EMAIL_BACKEND=smtp` and the `SMTP_*` environment variables; no code or dependency changes. Python's standard `smtplib` is used, with STARTTLS on 587 or implicit TLS on 465.

- **Default stays "log"**, which development relies on to follow reset links. Outside development, the API and worker log an error at start-up if mail would only reach the log.
- **A failed send never breaks the caller.** `send_safely` logs the failure (without the address or any credential) and returns False. A password reset answers the same either way, so a provider outage cannot be used to probe for accounts. An alert or monthly report stays in the app with `sent_at` empty.
- **Failed jobs email operators** listed in `OPS_ALERT_EMAILS` (the M1 "alert on failed jobs" item). The failure is also on `/admin/audit`.
- **Plain text only** for now, UTF-8, so Bangla arrives intact. HTML templates, bounce handling and web push are later work.
- **Still the owner's call:** which provider, and verifying the sending domain (SPF, DKIM, DMARC) for analysisace.com with it. Until the domain is verified, mail may land in spam.

## D25. Email verification is soft: nothing is blocked, emails wait (2026-11-24)

Sign-up sends a link to confirm the address (`/verify-email?token=...`, valid 48 hours, `EMAIL_VERIFICATION_TTL_HOURS`). Until it is opened:

- **The person can use everything.** Blocking sign-in on a mail delivery we do not control yet would lose people at the first step.
- **Alert and monthly-report emails are held back**, so a mistyped address never receives someone's net worth or Zakat figures. The notices still appear in the app. Password-reset emails still go out, because they are how an account is recovered.
- **A banner under the menu** says so and offers "Send the link again". A new link makes earlier ones stop working.
- **The link page confirms on a button press**, not on load: mail scanners open links before the person does and would use the link up.
- Demo users and administrators created with `scripts/create_admin.py` are marked confirmed. Only the token's hash is stored, as for password resets, and deleting an account deletes its tokens.

## D26. Browser push with VAPID keys; the alert rule decides (2026-11-24)

Alerts can reach a phone or computer as a browser notification (Web Push, `pywebpush`). The existing alert channel choice decides which alerts push: "Browser notification" or "Both". The notice is in the app either way.

- **Off until keys exist.** Push needs a VAPID key pair (`scripts/generate_vapid_keys.py`) in `WEBPUSH_PUBLIC_KEY` and `WEBPUSH_PRIVATE_KEY`. Without them the Alerts page says notifications are not switched on yet, and nothing is sent.
- **Per device.** A person turns notifications on in each browser on the Alerts page. The browser subscribes with the public key; the subscription is saved through a server action (the browser never calls the API). Turning it off unsubscribes the browser and deletes the row.
- **Only real push services.** A subscription endpoint must be HTTPS on a browser vendor's push host (Google, Mozilla, Apple, Microsoft), so the server never posts to an address a client made up.
- **Dead subscriptions are dropped** when the push service answers 404 or 410. Other failures are logged and do not break the alert job.
- **The service worker** (`/sw.js`) only shows notifications and opens pages on this site; it caches nothing.
- **Short text.** Title from the alert's email subject, body from its first line (up to 180 characters), and a link to the page the notice points to.
- **Testing limit.** Headless test browsers always report notifications as blocked, so a real subscribe is not covered by the browser tests; the server side is covered by unit tests with a stand-in sender. iPhones need the site added to the home screen before Safari allows push.

## D27. Production email goes through Gmail SMTP (2026-11-26)

The owner chose Gmail SMTP. Nothing in the code is Gmail-only; the defaults and two details are:

- **Settings** come only from the environment, filled in on the production server: `EMAIL_BACKEND=smtp`, `SMTP_USERNAME` (the Gmail address) and `SMTP_PASSWORD` (a Google app password; the account needs 2-Step Verification). `SMTP_HOST` defaults to `smtp.gmail.com`, port 587 with STARTTLS.
- **From is the account.** Gmail rewrites any From that is not the account or a verified "Send mail as" alias, and mismatched senders land in spam. With `EMAIL_FROM` empty, mail goes out as `analysisACE <SMTP_USERNAME>` (`EMAIL_FROM_NAME` sets the name). Start-up warns if `EMAIL_FROM` is set to another address.
- **App password spaces.** Google displays the password in four groups; the spaces are removed for Gmail hosts only.
- **Start-up check.** With `EMAIL_BACKEND=smtp`, a missing host, username or password is logged as an error.
- **Limits.** A personal Gmail account sends about 500 messages a day (Google Workspace about 2,000). That is enough for password resets, verification and alerts at launch. The monthly report goes to every user on the 1st, so past a few hundred users it needs a Workspace account or a transactional provider; switching is a change of the `SMTP_*` variables.
