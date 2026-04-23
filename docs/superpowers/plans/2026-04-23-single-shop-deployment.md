# Single-Shop Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the stack safe to leave running in a shop: HTTPS on the LAN, nightly Postgres backups on a mounted volume, a one-command update script, and a restore runbook.

**Architecture:** Add a `certs/` volume and switch `nginx` to listen on 443 with a self-signed cert + HTTP→HTTPS redirect. Add a lightweight `backup` service to `docker-compose.yml` that runs `pg_dump` once a day into a host-mounted `backups/` directory and retains the last 14. Ship a `scripts/update.sh` that pulls, rebuilds, and runs migrations. Document restore in `docs/ops/backup-restore.md`.

**Tech Stack:** docker-compose, nginx, `postgres:16-alpine` (already includes `pg_dump`), plain bash.

---

### Task 1: nginx listens on 443 with TLS

**Files:**
- Modify: `nginx.conf`
- Modify: `docker-compose.yml`
- Create: `scripts/generate-cert.sh`

- [ ] **Step 1: Write cert generation script**

`scripts/generate-cert.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="$(dirname "$0")/../certs"
mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/server.crt" && -f "$CERT_DIR/server.key" ]]; then
  echo "cert already exists in $CERT_DIR — delete files there to regenerate"
  exit 0
fi

CN="${1:-openmarket.local}"
openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1"

echo "wrote $CERT_DIR/server.crt (CN=$CN)"
echo "install $CERT_DIR/server.crt in each client browser/keychain to avoid warnings"
```

Make executable: `chmod +x scripts/generate-cert.sh`.

- [ ] **Step 2: Update nginx.conf**

Replace the `server { listen 80; ... }` block in `nginx.conf` with:

```nginx
    server {
        listen 80;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        ssl_certificate /etc/nginx/certs/server.crt;
        ssl_certificate_key /etc/nginx/certs/server.key;
        ssl_protocols TLSv1.2 TLSv1.3;

        location /api/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            root /usr/share/nginx/html/store;
            try_files $uri $uri/ /index.html;
        }

        location = /admin { return 301 /admin/; }
        location /admin/ {
            alias /usr/share/nginx/html/admin/;
            try_files $uri $uri/ /admin/index.html;
        }

        location = /pos { return 301 /pos/; }
        location /pos/ {
            alias /usr/share/nginx/html/pos/;
            try_files $uri $uri/ /pos/index.html;
        }
    }
```

- [ ] **Step 3: Update docker-compose.yml nginx service**

In `docker-compose.yml`, change the `nginx` service's `ports` and `volumes`:

```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - ./frontend/packages/store/dist:/usr/share/nginx/html/store:ro
      - ./frontend/packages/admin/dist:/usr/share/nginx/html/admin:ro
      - ./frontend/packages/pos/dist:/usr/share/nginx/html/pos:ro
    depends_on:
      - api
```

- [ ] **Step 4: Commit**

```bash
git add nginx.conf docker-compose.yml scripts/generate-cert.sh
git commit -m "feat(deploy): HTTPS on 443 with self-signed cert"
```

---

### Task 2: Nightly Postgres backup service

**Files:**
- Create: `scripts/backup.sh`
- Modify: `docker-compose.yml`
- Create: `backups/.gitkeep`

- [ ] **Step 1: Write backup script**

`scripts/backup.sh`:

```bash
#!/usr/bin/env sh
set -eu

# Runs inside the backup container. Uses env vars passed from compose.
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT="/backups/openmarket-$STAMP.sql.gz"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  | gzip -9 > "$OUT"
echo "wrote $OUT"

# Retain last 14 dumps; delete older.
ls -1t /backups/openmarket-*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
```

- [ ] **Step 2: Add `backup` service to docker-compose.yml**

Append to the `services:` block:

```yaml
  backup:
    image: postgres:16-alpine
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      POSTGRES_DB: openmarket
      POSTGRES_USER: openmarket
      POSTGRES_PASSWORD: ${DB_PASSWORD:-openmarket}
    volumes:
      - ./backups:/backups
      - ./scripts/backup.sh:/backup.sh:ro
    entrypoint: ["/bin/sh", "-c"]
    command: |
      "chmod +x /backup.sh && \
       while true; do \
         /backup.sh || echo 'backup failed'; \
         sleep 86400; \
       done"
```

- [ ] **Step 3: Create the backups dir placeholder**

```bash
mkdir -p backups && touch backups/.gitkeep
```

Add to `.gitignore` if one exists (append):

```
backups/*.sql.gz
```

- [ ] **Step 4: Commit**

```bash
git add scripts/backup.sh docker-compose.yml backups/.gitkeep .gitignore
git commit -m "feat(deploy): nightly pg_dump backup service with 14-day retention"
```

---

### Task 3: One-command update script

**Files:**
- Create: `scripts/update.sh`

- [ ] **Step 1: Write script**

`scripts/update.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> git pull"
git pull --ff-only

echo "==> build frontends"
(cd frontend && pnpm install --frozen-lockfile && pnpm build)

echo "==> rebuild + restart api"
docker compose build api
docker compose up -d db api nginx backup

echo "==> run migrations"
docker compose exec -T api alembic upgrade head

echo "==> done. current versions:"
docker compose ps
```

Make executable: `chmod +x scripts/update.sh`.

- [ ] **Step 2: Commit**

```bash
git add scripts/update.sh
git commit -m "feat(deploy): one-command update script"
```

---

### Task 4: Backup/restore runbook

**Files:**
- Create: `docs/ops/backup-restore.md`

- [ ] **Step 1: Write runbook**

`docs/ops/backup-restore.md`:

```markdown
# Backup & Restore

## Where backups live

Every 24h the `backup` service writes a gzipped `pg_dump` to `./backups/`.
The last **14** files are kept; older are deleted automatically.

```
backups/openmarket-2026-04-23T02-00-00Z.sql.gz
backups/openmarket-2026-04-22T02-00-00Z.sql.gz
...
```

We recommend replicating `./backups/` off-box (e.g. to a USB drive or
NAS) via `rsync` in a system cron — losing the NUC's disk would
otherwise take the backups with it.

## Manual backup (before risky ops)

```bash
docker compose exec backup /backup.sh
```

## Restore

1. **Stop the api** so nothing writes during restore:

```bash
docker compose stop api
```

2. **Wipe the live database** and recreate it empty:

```bash
docker compose exec db psql -U openmarket -d postgres \
  -c "DROP DATABASE openmarket;" -c "CREATE DATABASE openmarket;"
```

3. **Pipe the chosen dump back in:**

```bash
gunzip -c backups/openmarket-2026-04-23T02-00-00Z.sql.gz \
  | docker compose exec -T db psql -U openmarket -d openmarket
```

4. **Start the api again:**

```bash
docker compose start api
```

5. **Verify** by loading the admin, checking a recent order, and ringing
   up a 1-cent test sale.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ops/backup-restore.md
git commit -m "docs: backup/restore runbook"
```

---

## Self-review

- Spec coverage: HTTPS (T1), nightly backup (T2), update script (T3), restore docs (T4).
- No placeholders: every script is complete.
- Consistency: all scripts live under `scripts/`; all docs under `docs/ops/`.
