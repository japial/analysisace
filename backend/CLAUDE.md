# Backend

FastAPI API, analytics, ingestion and scheduled jobs. Root rules in [../CLAUDE.md](../CLAUDE.md) apply here; commands are listed there.

## Where things go

| Path | Holds | Rules |
|-|-|-|
| `app/api/v1/` | HTTP routes | Thin. Read precomputed rows; no heavy computation on request (API p95 under 300 ms). |
| `app/schemas/` | Pydantic request and response models | Data-derived responses use `Envelope` from `schemas/common.py` (`data`, `as_of`, `sources`). |
| `app/models/` | SQLAlchemy tables | Import every new model in `models/__init__.py` or Alembic will not see it. |
| `app/services/` | Use cases that read and write the database | The caller commits. Services call `session.flush()`, never `commit()`. |
| `app/analytics/` | Pure calculations (adjustment, later regression, XIRR, Zakat) | No database access, no I/O. Inputs and outputs are plain values so each formula has worked-example tests. |
| `app/ingestion/adapters/` | One class per data source | Fetch and parse only; never write to the database. Implement a protocol from `adapters/base.py`. |
| `app/jobs/` | Worker process and job registry | Register a job in `JOBS` under its name from `config/schedules.yaml`. |
| `app/core/` | Settings, database session, config loader, trading calendar | |
| `alembic/versions/` | Migrations | Autogenerate, then read the file before committing. |
| `tests/` | pytest | See below. |

## Conventions

- **Money and ratios are `Decimal`.** Columns use `Numeric`. Never `float` for money. JSON carries decimal strings.
- **Do not name a column annotation after its type.** `date: Mapped[date]` breaks later annotations in the same class. Models import `datetime as dt` and use `dt.date`; dataclasses name the field `day`.
- **Portable column types.** Use `Uuid` and `JSONType` from `models/base.py` so unit tests run on SQLite. Anything PostgreSQL-only needs a test that runs in CI against Postgres.
- **Every market data row has a `source_id`.** Create one `Source` row per fetch and attach it.
- **Rules come from YAML.** Read thresholds through `app.core.app_config.get_config("<domain>")`. If you change a file in `config/`, bump its `version`; the worker refuses to start on a changed file with an unchanged version.
- **Trading days** come from `app.core.trading_calendar`. Never test `weekday()` directly.
- **Datetimes are timezone-aware UTC** (`datetime.now(UTC)`). Ruff's `DTZ` rules enforce this.
- **Quality failures become `data_issue` rows** and the bad rows are not stored (PRD section 8).

## Accounts and permissions

- Protect a route with `CurrentUser` (any signed-in user) or `Depends(require_permission(Permission.X))` from `app/api/deps.py`. Check permissions, never role names.
- Add a permission in `app/core/permissions.py` and give it to roles there. Add its name and description to both message files in the frontend.
- Refuse a request by raising `AuthError("CODE", status)`. The code is part of the API contract: add its translation under `errors` in both message files.
- Never log or return passwords, tokens or reset links. Store only `hash_token(token)`.
- Write an `audit(...)` entry for every admin action and every change to roles, access or consents. Audit entries hold user ids, never emails or names.
- A new personal data table must be added to `_HOUSEHOLD_TABLES` or `_CHILD_TABLES` in `services/household_data.py` (or to `export_user_data` and `delete_account` in `services/auth.py` if it belongs to the user, not a household), so export and deletion cover it (FR23.4).
- Rows that reference another table need that row flushed first: models define no ORM relationships, so SQLAlchemy does not order inserts for you. Call `session.flush()` after adding parents.
- Demo data lives in `app/seed/`. Keep it fictional and labelled (docs/DECISIONS.md, D15). Add demo rows there whenever a feature gets a new table.
- The first start of the local database after an unclean stop can take 30+ seconds while PostgreSQL recovers. `scripts/dev_db.py` waits up to 2 minutes for it; stop the database with `--stop` (or `.\dev -Stop`) to avoid the delay.

## Tests

- Unit tests use the `session` and `client` fixtures in `tests/conftest.py` (in-memory SQLite).
- Name tests after the behaviour and cite the requirement in the docstring or name, for example `test_zakat_gold_nisab_fr13_2`.
- Every formula in `analytics/` needs worked examples with numbers a person can check by hand, plus property tests (Hypothesis) where an invariant exists.
- Coverage target is 80% for `analytics/` and `services/`.
- After adding or changing a model: start the local database (`scripts/dev_db.py`), autogenerate a migration, then run `alembic upgrade head` and `alembic check`.

## Adding a data source

1. Define or reuse a protocol and batch dataclass in `ingestion/adapters/base.py`.
2. Write the adapter. Check the site's terms of use first; if scraping is not allowed, stop and ask.
3. Write or extend a service in `services/` that stores the batch and records quality issues.
4. Register the job in `app/jobs/worker.py` and confirm its schedule exists in `config/schedules.yaml`.
5. Test the adapter against a saved sample file in `tests/fixtures/`, never against the live site.
