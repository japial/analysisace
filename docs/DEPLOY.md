# Deploying analysisACE with Docker

This guide puts the whole app on one Linux server with Docker Compose, behind HTTPS. It uses `docker-compose.prod.yml`. The other compose file, `docker-compose.yml`, is for local use and CI only. Decision D40 in [DECISIONS.md](DECISIONS.md) explains the choices.

## What runs

```
Internet ──443──> caddy ──> web (Next.js) ──> api (FastAPI) ──> db (PostgreSQL 16)
                  HTTPS                          worker ──────────┘
                                                 backup ──> ./backups (daily)
```

| Service | Job | Reachable from outside |
|-|-|-|
| `caddy` | HTTPS, gets and renews the certificate by itself, security headers | Yes, ports 80 and 443 |
| `web` | Renders every page and calls the API from the server | No |
| `api` | The FastAPI app | No |
| `worker` | Scheduled jobs from `config/schedules.yaml`: prices, alerts, digests, monthly report, bounces | No |
| `migrate` | Applies database migrations on every start, then exits | No |
| `db` | PostgreSQL 16, data in the `pgdata` volume | No |
| `backup` | A database dump and a copy of the documents once a day | No |

Encrypted documents (FR25.4) live in the `documents` volume.

## What you need

- **A server:** Ubuntu 22.04 or 24.04 with at least 2 CPU cores, 4 GB of memory and 40 GB of disk. The web app is built on the server, and the build needs about 2 GB of memory.
- **A domain name:** an A record for, say, `app.analysisace.com` pointing at the server's IP address, set before the first start. Caddy needs it to get the certificate.
- **Open ports:** 22 for SSH, plus 80 and 443.
- **Access to the private repository** from the server, for example with a read-only deploy key.
- **A Gmail account with an app password,** for sign-up confirmations and password resets (D27).

## First deployment

All commands run on the server.

**1. Install Docker** and the Compose plugin, following Docker's guide for Ubuntu: https://docs.docker.com/engine/install/ubuntu/

Then allow only the ports in use:

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
```

**2. Get the code** from the `main` branch:

```bash
git clone --branch main <repository-url> analysisace
cd analysisace
```

**3. Write the settings file:**

```bash
cp .env.production.example .env
openssl rand -hex 24                       # paste as POSTGRES_PASSWORD
openssl rand -base64 32 | tr '+/' '-_'     # paste as DATA_ENCRYPTION_KEY
nano .env
```

Fill in `DOMAIN`, `ACME_EMAIL`, `POSTGRES_PASSWORD`, `DATA_ENCRYPTION_KEY`, `SMTP_USERNAME` and `SMTP_PASSWORD`.

Save `DATA_ENCRYPTION_KEY` in a password manager now. Without it, stored account numbers and documents cannot be read, and backups don't help.

**4. Start everything:**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

The first build takes several minutes. Compose stops at once with a clear message if a required setting is missing.

**5. Check it.** Every service should be `running` or `healthy`, and `migrate` should have exited with code 0:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f caddy web api
```

Then open `https://<DOMAIN>`. The first visit can take a few seconds while Caddy gets the certificate.

**6. Create the first administrator.** It asks for a password:

```bash
docker compose -f docker-compose.prod.yml run --rm api python scripts/create_admin.py you@example.com "Your Name"
```

**7. Optional: browser push (D26).** Generate keys, paste them into `.env`, then apply them:

```bash
docker compose -f docker-compose.prod.yml run --rm --no-deps api python scripts/generate_vapid_keys.py
docker compose -f docker-compose.prod.yml up -d
```

Commands are shorter with an alias:

```bash
alias dc='docker compose -f docker-compose.prod.yml'
```

## Updating

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run by themselves before the API and the worker start again.

To keep the previous build for a rollback, set a new `IMAGE_TAG` in `.env` before building, such as the date. To roll back, set the old tag again and run `up -d` without `--build`.

Migrations do not roll back on their own, so take a backup first (see below) before an update that changes the database.

## Backups

The `backup` service writes into `BACKUP_DIR` (default `./backups`) once a day and deletes files older than `BACKUP_KEEP_DAYS`:
- `db-<time>.dump`: the database
- `documents-<time>.tar.gz`: the encrypted documents

These files are still on the same server. Copy them somewhere else every day, for example with `rclone` to cloud storage. Keep them apart from `DATA_ENCRYPTION_KEY`.

To make a backup now:

```bash
docker compose -f docker-compose.prod.yml restart backup
```

**To restore** (stop the app first):

```bash
dc stop web api worker
dc cp backups/db-<time>.dump db:/tmp/restore.dump
dc exec db pg_restore --clean --if-exists -U analysisace -d analysisace /tmp/restore.dump
dc run --rm --no-deps --user root -v "$PWD/backups:/backups:ro" api \
  sh -c "tar -xzf /backups/documents-<time>.tar.gz -C /srv/data/documents && chown -R app /srv/data/documents"
dc up -d
```

## Day to day

| Task | Command |
|-|-|
| Status | `dc ps` |
| Logs | `dc logs -f --tail 200 api worker` (logs rotate at 5 × 10 MB per service) |
| Restart one service | `dc restart api` |
| Database shell | `dc exec db psql -U analysisace analysisace` |
| Stop everything | `dc down` (data stays in the volumes; `down -v` would delete it) |

Failed scheduled jobs are emailed to `OPS_ALERT_EMAILS` and listed on `/admin/audit`.

## Rules for production

- **Never run `scripts/seed_demo.py` on a server.** It refuses outside development, and it must stay that way.
- **Keep `ENVIRONMENT=production`.** The compose file sets it. Development mode would make up an encryption key and relax the rate limits.
- **Use HTTPS only.** The sign-in cookie is marked secure in production, so signing in does not work over plain HTTP.
- **The API is not published.** Firm API keys (F9) will need a public route to the API. Add one to `deploy/Caddyfile` only when firm features are switched on (Q4).
- **Run exactly one `worker`.** Two would run every scheduled job twice.

## Troubleshooting

| What you see | Likely cause |
|-|-|
| Compose says `Set ... in .env` | A required value in `.env` is empty. |
| The certificate fails in the `caddy` logs | DNS does not point at the server yet, or port 80 is blocked. |
| "Bad gateway" (502) | The web app is not healthy yet. Check `dc logs web api`. |
| Signing in does nothing | The site is not on HTTPS, or `DOMAIN` does not match the address in the browser. |
| No emails arrive | `EMAIL_BACKEND` is not `smtp`, or the Gmail app password is wrong. Check `dc logs api worker`. |
| Uploading a document fails | `DATA_ENCRYPTION_KEY` is missing or not a valid key. |
