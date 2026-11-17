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
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND / ".pgdata"
ENV_FILE = BACKEND / ".env"


def _write_database_url(url: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.startswith("DATABASE_URL=")]
    lines.append(f"DATABASE_URL={url}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _wait_until_ready(timeout_s: float = 120) -> bool:
    """Wait for postmaster.pid to report 'ready'.

    After an unclean shutdown (window closed, PC restarted without --stop), Postgres runs
    crash recovery on start. On Windows that can take 30+ seconds, longer than pgserver's
    fixed 10 second pg_ctl timeout, so the start "fails" while the server is still coming up.
    """
    pid_file = DATA_DIR / "postmaster.pid"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if "ready" in pid_file.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            pass
        time.sleep(1)
    return False


def main() -> int:
    try:
        import pgserver
    except ImportError:
        print('pgserver is not installed. Run: python -m pip install -e ".[dev,localdb]"')
        return 1

    # cleanup_mode=None keeps the server running after this script exits.
    try:
        server = pgserver.get_server(DATA_DIR, cleanup_mode=None)
    except subprocess.TimeoutExpired:
        print("Database is recovering from an unclean shutdown; waiting for it to be ready...")
        if not _wait_until_ready():
            print(f"Database did not become ready. See {DATA_DIR / 'log'}")
            return 1
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
