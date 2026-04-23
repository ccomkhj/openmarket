# Go-Live Checklist

Work top-to-bottom. Don't skip. Each item is binary: done or not.

## Server (NUC) setup

- [ ] Docker + Docker Compose installed
- [ ] Repo cloned to `/opt/openmarket` (or similar)
- [ ] `.env` copied from `.env.example` and filled in:
  - [ ] `DB_PASSWORD` — strong, 24+ chars
  - [ ] `DATABASE_URL` — matches `DB_PASSWORD`
  - [ ] `SESSION_SECRET_KEY` — `openssl rand -hex 32`
  - [ ] `MERCHANT_*` — real company data (§14 UStG)
  - [ ] `FISKALY_*` — real TSE credentials from Fiskaly dashboard
  - [ ] `TERMINAL_HOST` — real card terminal IP (or blank if no card)
  - [ ] `PRINTER_*` — matches connected ESC/POS printer
- [ ] `chmod 600 .env`
- [ ] TLS cert generated: `./scripts/generate-cert.sh your-domain`
- [ ] Cert installed on every client device (admin laptop, POS, tablet)

## First run

- [ ] `(cd frontend && pnpm install && pnpm build)`
- [ ] `docker compose up -d`
- [ ] `docker compose exec api alembic upgrade head` — migrations green
- [ ] `docker compose ps` — all services `healthy`
- [ ] Open `https://openmarket.local/admin` — Setup form appears
- [ ] Create owner, enroll MFA, scan QR code
- [ ] Create backup owner (break-glass, keep password in safe)
- [ ] Create manager(s) and cashier(s) (with PINs)
- [ ] **Admin → Settings → Store Info** — values match `.env`

## Data seed

- [ ] CSV product catalog imported (Admin → Products → Import CSV)
- [ ] Starting inventory set via Products page (or CSV follow-up)
- [ ] Tax rates configured (19% and 7% for DE)
- [ ] Shipping methods configured (if running online shop)
- [ ] Location(s) configured

## Hardware verification — DO NOT SKIP

- [ ] Receipt printer prints a test receipt (ring up a 1-cent item, pay cash)
- [ ] Cash drawer pulses open on cash payment
- [ ] Card terminal authorizes a 1 EUR test card (refund it)
- [ ] TSE signature appears on the test receipt
- [ ] Storno the test sales so they don't pollute Z-report

## Smoke test

- [ ] `OWNER_EMAIL=owner@... OWNER_PASSWORD=... ./scripts/smoke-test.sh`
  prints `ALL OK`

## Backups

- [ ] `./backups/` exists and `backup` service is running
- [ ] Wait 24h (or `docker compose exec backup /backup.sh`) and confirm a `.sql.gz` file appears
- [ ] Off-box replication configured (rsync to USB / NAS — add to system cron)
- [ ] Restore drill: on a spare machine, restore the latest backup per `docs/ops/backup-restore.md`; confirm a known order is present

## Staff

- [ ] Every cashier has a PIN
- [ ] `docs/ops/cashier-quickcard.md` printed and taped next to each POS
- [ ] Owner/manager knows how to run Z-Report and DSFinV-K export
- [ ] Owner knows where backups are and how to restore

## Legal (DE)

- [ ] USt-IdNr. printed on a test receipt (check `docs/ops/store-info.md`)
- [ ] TSE active (Admin → Settings → Store Info says "configured", and health/fiskaly endpoint returns `online: true`)
- [ ] Online store (if active) has imprint + privacy + cookie consent
- [ ] Bookkeeper briefed on DSFinV-K export location

## Pilot

- [ ] Run 1 week in parallel with the old system OR on a single register in a quiet store
- [ ] Compare daily totals to the old system each evening
- [ ] Cutover only after 5 consecutive clean days
