# analysisACE

Bangladesh-first personal finance web app that helps a household grow its ACE: **A**ssets (what it owns and owes, Zakat, wealth statement), **C**apital (the part put to work: shares, sukuk, deposits, FIRE and goals) and **E**arnings (income, costs, savings, tax). DSE stocks are one kind of capital; the Shariah screen and macro analytics are an optional tool layer for people who hold shares, not the product's centre. Landing page, menu and roadmap lead with ACE and My money. A mobile app (Expo) comes later and will reuse `frontend/packages/*`.

- Full spec: [docs/PRD.md](docs/PRD.md). Requirement IDs (`FR1.2`, `F13`, `Q4`) refer to it.
- How the pieces fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Why choices were made: [docs/DECISIONS.md](docs/DECISIONS.md)
- What is built and what is next: [docs/ROADMAP.md](docs/ROADMAP.md). Update it when a milestone item is finished.

## Layout

| Path | Contents |
|-|-|
| `backend/` | FastAPI API, analytics, ingestion adapters, scheduled jobs, Alembic migrations. See [backend/CLAUDE.md](backend/CLAUDE.md). |
| `frontend/` | npm workspaces: `apps/web` (Next.js), `packages/core`, `packages/i18n`. See [frontend/CLAUDE.md](frontend/CLAUDE.md). |
| `config/` | Versioned YAML: Shariah thresholds, Zakat rules, regime rules, schedules, excluded periods, trading calendar. |
| `docs/` | PRD, architecture, decisions, roadmap. |
| `coming-soon/` | The static page currently live on analysisACE.com. Published by `netlify.toml`. Do not mix app code into it. |

## Commands

The dev machine is Windows with Python 3.12 and Node 26. It has no Docker, no `make` and no local Postgres, so run the checks directly. Docker Compose is used in CI and on servers.

Backend (run from `backend/`, with the virtual environment at `backend/.venv`):

- Set up: `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev,localdb]"`
- Tests: `.venv/Scripts/python -m pytest` (in-memory SQLite, no database needed)
- Lint: `.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m ruff format --check .`
- Types: `.venv/Scripts/python -m mypy app`
- Local Postgres: `.venv/Scripts/python scripts/dev_db.py` starts a bundled PostgreSQL 16, writes `DATABASE_URL` to `backend/.env` and applies migrations. Add `--stop` to stop it.
- Run API: `.venv/Scripts/python -m uvicorn app.main:app --reload` (API docs at http://localhost:8000/api/v1/docs)
- Run worker: `.venv/Scripts/python -m app.jobs.worker`
- First admin: `.venv/Scripts/python scripts/create_admin.py you@example.com "Your Name"` (asks for a password)
- Demo data for development: `.venv/Scripts/python scripts/seed_demo.py` loads fictional companies with five years of synthetic prices, macro series, events, sukuk, and a demo household, analyst and firm. It prints the demo sign-ins. Never run it in production.
- New migration: `.venv/Scripts/python -m alembic revision --autogenerate -m "<msg>"` (local Postgres must be running)

Frontend (run from `frontend/`):

- Set up: `npm install`
- Dev server: `npm run dev` (web on http://localhost:3000; expects the API on http://localhost:8000)
- Tests: `npm test`
- Lint and types: `npm run lint && npm run typecheck`
- Build: `npm run build`
- Browser tests: `npm run test:e2e` (the database, API and web app must be running; set `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` to include the admin test)

Everything together on the Windows dev machine: `.\dev` from the repo root starts the local database, then opens the API and the web app in their own windows. Add `-Worker` to also start the worker. `.\dev -Stop` stops everything (API, web app, worker and database).

Everything together (where Docker exists): `docker compose up` from the repo root.

## Hard rules (never break)

- Never give investment advice: no buy, sell or hold wording, target prices or trading signals in the UI, API, emails or reports. Use descriptive wording ("historically moved", "drift from your target").
- Never store or show the DSE's licensed DSES constituent list. Only the index level is allowed. analysisACE runs its own screening.
- No crypto exchange or wallet integrations.
- Every analytical page, email and PDF shows: "Historical analysis for education only. Not investment advice." (i18n key `common.disclaimer`).
- Every number shown to users is traceable to a source record and a computation timestamp. Every data-derived API response includes `as_of` and `sources`.
- Do not scrape a site in a way that breaks its terms of use. Each data source sits behind an adapter interface.

## Conventions

- Thresholds, Zakat rules, nisab weights, benchmarks, schedules and excluded date ranges live only in `config/*.yaml`, never as constants in code. Many values are provisional until a Shariah advisor approves them.
- Money is BDT as `Decimal` (Python) and decimal strings in JSON. Never float.
- Dates are stored in UTC and shown in Asia/Dhaka. The DSE trades Sunday to Thursday; use `app.core.trading_calendar`, never `weekday()` checks.
- All user-facing strings go through i18n, in both `bn` and `en`.
- When blocked by an open question (PRD section 17), build the stated default behind a config flag and add `TODO(owner): Qn` at the spot.
- Reference PRD requirement IDs in test names, commit messages and comments on functions that implement a requirement.
- Build in milestone order (PRD section 14). Add or update tests with every change to `analytics/` or `services/`.
- The UI is the licensed Metronic 9 theme (Layout 9). Keep this repository private and never commit the theme download itself (docs/DECISIONS.md, D11).
- Work happens on `develop`; `main` is what Netlify deploys.
