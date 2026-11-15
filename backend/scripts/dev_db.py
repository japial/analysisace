"""Local PostgreSQL for development on a machine without Docker.

    python scripts/dev_db.py          start (or reuse) the database and apply migrations
    python scripts/dev_db.py --stop   stop it

Uses the `pgserver` package, which bundles PostgreSQL 16 binaries. Data lives in
backend/.pgdata. The connection URL changes port between starts, so this script writes it
to backend/.env as DATABASE_URL, where the API, the worker and Alembic pick it up.

Install once with: python -m pip install -e ".[dev,localdb]"
"""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / ".pgdata"
ENV_FILE = BACKEND / ".env"


def _write_database_url(url: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.startswith("DATABASE_URL=")]
    lines.append(f"DATABASE_URL={url}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        import pgserver
    except ImportError:
        print('pgserver is not installed. Run: python -m pip install -e ".[dev,localdb]"')
        return 1

    # cleanup_mode=None keeps the server running after this script exits.
    server = pgserver.get_server(DATA_DIR, cleanup_mode=None)
    if "--stop" in sys.argv:
        server.cleanup()
        print("Local database stopped.")
        return 0

    url = server.get_uri().replace("postgresql://", "postgresql+psycopg://", 1)
    _write_database_url(url)
    print(f"Local database running. DATABASE_URL written to {ENV_FILE.name}:\n  {url}")
    return subprocess.call([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND)


if __name__ == "__main__":
    raise SystemExit(main())
