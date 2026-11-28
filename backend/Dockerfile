# Build from the repo root so the image can include config/:
#   docker build -f backend/Dockerfile .
# One image runs the API, the worker, migrations and the admin scripts.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CONFIG_DIR=/srv/config \
    DOCUMENT_STORAGE_DIR=/srv/data/documents \
    WEB_CONCURRENCY=2

WORKDIR /srv/backend

COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install -e .

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
# create_admin.py and generate_vapid_keys.py are run with `docker compose run`.
COPY backend/scripts ./scripts
COPY config /srv/config

# Encrypted documents (FR25.4) live in a volume mounted here; a new named volume takes
# this directory's owner, so the app user can write to it.
RUN useradd --system --no-create-home --uid 10001 app \
    && mkdir -p /srv/data/documents \
    && chown -R app /srv/data
USER app

EXPOSE 8000
# Uvicorn reads the number of worker processes from WEB_CONCURRENCY.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
