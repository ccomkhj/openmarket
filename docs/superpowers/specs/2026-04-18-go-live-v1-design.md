# OpenMarket Go-Live v1 — Design Spec

Making OpenMarket production-ready for a single-cashier German supermarket opening in 2–3 months. Offline/POS channel only; online channel explicitly deferred.

## Context

OpenMarket today is an MVP: FastAPI + Postgres backend, three React frontends (store/admin/pos), docker-compose deployment, realtime inventory via WebSocket, barcode + OCR scanner, partial fulfillment/cancellation support. It has no authentication, no payment integration, no fiscal compliance, wide-open CORS, and no backups. None of these gaps are surprising — they were explicit non-goals in the original MVP spec.

This spec closes the gaps that stand between "MVP" and "a shop in Germany can legally accept real money with this, on day one."

## Scope — what this spec covers

1. Fiscal compliance (KassenSichV + GoBD + DSFinV-K + Belegausgabepflicht)
2. Payment flow (ZVT card terminal, cash, cash drawer, Kassenbuch)
3. Weighed-produce data model
4. Staff authentication & authorisation
5. Receipt printing
6. Minimal security baseline
7. Minimal backups & disaster recovery
8. Minimal observability
9. Testing & go-live checklist

## Non-goals — explicit deferrals

- Online channel (customer accounts, checkout, delivery, online payments) — Phase 2.
- Multi-cashier simultaneous operation — day-one is single-cashier.
- Offline-mode POS for full internet outage — only brief fiskaly blips are tolerated.
- Self-checkout, integrated scale hardware, weight-embedded-barcode PLUs.
- Full security hardening (CSP, CSRF middleware, egress firewall, Tailscale, Dependabot) — Phase 2.
- Full backup/DR (WAL/PITR, cold-spare NUC, USB rotation, restore-drill automation) — Phase 2.
- Metrics/tracing infrastructure (Prometheus, log aggregation) — Phase 2.
- SSO, passkeys, customer-facing GDPR erasure UI.

**Phase 2 trigger** for the deferred security/backup/ops work: before the online channel launches, before any non-LAN access is enabled, or before the shop hits ~10k transactions/month — whichever comes first.

## Target deployment — physical shape

One NUC under the counter. One tablet / touchscreen for the cashier. One USB thermal receipt printer (Epson TM-m30III or Star TSP143 class). One USB-kicked cash drawer wired into the printer's RJ12 port. One ZVT-capable card terminal on the LAN via wired Ethernet. A UPS on the NUC's power. A cold-spare NUC in a drawer (same OS image). Off-site backup target at Hetzner Storage Box.

Network: NUC is the LAN server; everything else talks to it locally. Internet required only for fiskaly TSE signing, NTP, and nightly backups — never for the sales flow to complete under normal operation.

Process dependencies: Finanzamt Kasse registration (within 1 month of deployment), Steuerberater sign-off on DSFinV-K output before go-live, dry-run day with fake products before real customers, backup restore drill before go-live.

---

## 1. Fiscal compliance

**TSE provider:** fiskaly Cloud-TSE. Rationale: survives on-site hardware failure (signatures retained by fiskaly), simpler ops than USB TSE, the internet dependency is manageable via async signing fallback.

**New tables — all append-only, enforced by Postgres triggers rejecting UPDATE/DELETE.**

`pos_transaction` — one row per completed sale.

| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| client_id | uuid | Client-generated, idempotency key |
| cashier_user_id | int, FK users | Snapshot of logged-in cashier |
| started_at | timestamptz | Open of transaction |
| finished_at | timestamptz | After fiskaly finish_transaction |
| total_gross | numeric(10,2) | |
| total_net | numeric(10,2) | |
| vat_breakdown | jsonb | `{"7":{"net":..,"vat":..,"gross":..},"19":{...}}` |
| payment_breakdown | jsonb | `{"cash":..,"girocard":..,"card":..}` |
| receipt_number | int | Gap-free per fiscal year, Postgres sequence |
| linked_order_id | int, FK orders | Nullable |
| voids_transaction_id | uuid, FK self | Nullable; on a Storno row, points to the original it cancels. Original row is never modified. |
| tse_signature | text | Base64 signature from fiskaly |
| tse_signature_counter | bigint | |
| tse_serial | text | |
| tse_timestamp_start | timestamptz | |
| tse_timestamp_finish | timestamptz | |
| tse_process_type | text | "Kassenbeleg-V1" |
| tse_process_data | text | Canonical string hashed into signature |
| tse_pending | bool | True = signing failed, retry pending |

`pos_transaction_line` — one row per basket line, denormalised from `order_items`.

| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| pos_transaction_id | uuid, FK | |
| sku | text | Snapshot at sale time |
| title | text | Snapshot |
| quantity | numeric(10,3) | Integer for fixed items |
| quantity_kg | numeric(10,3) | Nullable, for weighed items |
| unit_price | numeric(10,4) | |
| line_total_net | numeric(10,2) | |
| vat_rate | numeric(5,2) | |
| vat_amount | numeric(10,2) | |
| discount_amount | numeric(10,2) | |

`kassenbuch_entry` — cash movements other than sales.

| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| entry_type | enum | `open`, `close`, `paid_in`, `paid_out`, `drop` |
| amount | numeric(10,2) | Signed |
| denominations | jsonb | Count per denomination, for open/close |
| reason | text | |
| cashier_user_id | int, FK | |
| timestamp | timestamptz | |

`tse_signing_log` — every fiskaly call, success and failure, for post-mortems.

| Column | Type | Notes |
|---|---|---|
| id | bigserial, PK | |
| pos_transaction_id | uuid, FK | Nullable (for non-transaction calls like export) |
| operation | text | `start_transaction`, `finish_transaction`, `export`, `retry` |
| attempted_at | timestamptz | |
| succeeded | bool | |
| error_code | text | Fiskaly error code on failure |
| error_message | text | |
| duration_ms | int | |

**New service — `FiscalService`.** Wraps fiskaly's REST API. Methods: `start_transaction(client_id)`, `finish_transaction(tx_id, process_data)`, `export_dsfinvk(date_range)`, `retry_pending_signatures()`.

**Sale flow.** `start_transaction` is called first (reserves a signature counter even on failed sales). Build the DSFinV-K `process_data` canonical string. Call `finish_transaction`. Write back signature fields. Print receipt. All within one DB transaction — no receipt prints without a signature stored.

**Fiskaly outage handling.** Retry with exponential backoff ~20s. On genuine failure: write `tse_pending = true`, print receipt with banner "TSE-Ausfall — Nachsignierung erforderlich", background job retries. Resumed signing closes the gap before daily export.

**Storno (corrections).** No DELETE or UPDATE on fiscal rows — ever. A wrong sale is cancelled by creating a new `pos_transaction` whose `voids_transaction_id` points to the original, with negative line quantities, also TSE-signed. The original row is never touched. To check whether a transaction was voided: `SELECT ... WHERE voids_transaction_id = :original_id`. UI has "Storno last/selected receipt" for cashiers.

**DSFinV-K export.** Admin UI button generates a ZIP for a date range: all required CSVs (`bonkopf.csv`, `bonpos.csv`, `cash_per_currency.csv`, `bonkopf_zahlarten.csv`, `tse.csv`, etc.) + `index.xml` + DTD. Format follows the BMF reference exactly. Also generated automatically at end-of-day into `/fiscal-archive/YYYY/MM/DD.zip`.

**Receipt number allocation.** Gap-free per fiscal year. Postgres sequence `nextval()` inside the same DB transaction that writes `pos_transaction`. Gaps are an audit red flag.

---

## 2. Payment flow

### Card — ZVT over TCP

Terminal sits on the LAN at a static IP. Protocol: **ZVT 700** (LAN variant). Library: `python-zvt`. Commands used: `06 01` Authorisation, `06 30` Reversal, `06 50` End-of-Day, `05 01` Diagnosis.

### Sale sequence — interlocking order

1. Cashier hits "Pay by card" → create `pos_transaction` (open), call fiskaly `start_transaction`.
2. `PaymentTerminalService.authorize(amount)` → terminal handles PIN/tap.
3. **Declined** → fiskaly `finish_transaction` with cancelled-attempt marker (legally required), show "try again or cash".
4. **Approved** → fiskaly `finish_transaction` with full basket, write signature, close `pos_transaction`, print receipt with TSE block + card merchant fields.
5. Fiskaly down at step 4 → unsigned-with-resign path from §1.
6. Crash between card charge and signing → startup recovery job finds open `pos_transaction` with successful ZVT auth, retries fiskaly, reprints marked "Beleg-Nachdruck nach Systemfehler".

### Cash

Cashier enters tendered, app shows change, fiskaly sign, ESC/POS drawer-open pulse, print. No external dependency besides fiskaly.

### Mixed payment

`payment_breakdown` JSON carries per-method amounts; receipt lists them separately. Required for DSFinV-K `cash_per_currency.csv`.

### Cash drawer

Opens only via ESC/POS pulse to the printer's RJ12 kick-out port. No on-demand drawer-open in the UI — every opening is a logged sale or a `kassenbuch_entry` with a reason.

### Kassenbuch — daily shift

**Open:** cashier logs in, enters opening cash count by denomination, `kassenbuch_entry(type='open', denominations=...)`. Opening total must match previous close; mismatches require a reason.

**During shift:** paid-ins and paid-outs each produce a `kassenbuch_entry` and open the drawer.

**Close / Tagesabschluss / Z-Report:** cashier counts cash by denomination; app computes expected cash = opening + cash sales + paid-ins − paid-outs; difference per denomination shown. Z-Report prints (sales by VAT rate, by payment method, transaction count, TSE signature counter start→end). ZVT End-of-Day runs against the terminal. Kassendifferenz is logged, not hidden.

### Receipt content (mandatory fields)

Merchant name + address + Steuernummer + USt-IdNr; date + time; receipt number; each line with title, qty, unit price, VAT rate, line total; VAT breakdown table reconciling to line totals; payment method(s); TSE block (serial, signature counter, signature, start + finish timestamps, process type, process data). Belegausgabepflicht satisfied by paper by default; digital (emailed PDF) is Phase 2.

### Deferred

SEPA direct debit, gift cards, meal vouchers. `payment_breakdown` JSON makes these additive — no schema change needed to add later.

---

## 3. Weighed-produce data model

Additions to existing `ProductVariant`:

| Column | Type | Notes |
|---|---|---|
| pricing_type | enum | `fixed` (default), `by_weight`, `by_volume` (hook only) |
| weight_unit | enum | `kg`, `g`, `100g` — display hint; internal always kg |
| min_weight_kg | numeric(10,3) | Nullable; rejects cashier typos |
| max_weight_kg | numeric(10,3) | Nullable; upper bound |
| tare_kg | numeric(10,3) | Nullable; default container weight |
| barcode_format | enum | `standard` (day-one), `weight_embedded_ean13` (Phase 2 hook) |

Additions to `order_items`:

| Column | Type | Notes |
|---|---|---|
| quantity_kg | numeric(10,3) | Nullable; populated for `by_weight` |

**POS flow for weighed item (day-one, no scale integration).** Cashier scans barcode / picks item. If `pricing_type = by_weight`, UI swaps qty-stepper for a kg numeric keypad showing €/kg prominently. Cashier reads counter scale's display, types kg. App validates against min/max, applies tare, adds line. Receipt renders `Äpfel Gala  0,452 kg × 2,49 €/kg = 1,13 €`.

**Rounding.** Line totals rounded to cents per line; VAT computed on rounded line totals. Matches Finanzamt audit expectations — DSFinV-K otherwise trips 1-cent reconciliation flags.

**Edge cases.**

- Negative weight for return supported as Storno line with negative kg.
- Pre-packaged weighed items assumed to be re-weighed at register day-one; barcode-encoded-weight is Phase 2 (hook present).
- Inventory decrement happens in the item's native unit (pieces for fixed, kg for weighed).

**Explicitly deferred.** Scale integration, weight-embedded EAN-13 parsing, volume-priced items.

---

## 4. Auth & staff accounts

**Two tables.**

`user`:

| Column | Type | Notes |
|---|---|---|
| id | int, PK | |
| email | text, unique | Nullable for cashier-only |
| password_hash | text | argon2id; nullable for cashier-only |
| full_name | text | |
| role | enum | `owner`, `manager`, `cashier` |
| pin_hash | text | argon2id, 4–6 digit, only for cashier role |
| pin_locked_until | timestamptz | Rate-limit |
| active | bool | |
| mfa_totp_secret | text | Required for owner, optional for manager |
| created_at | timestamptz | |
| last_login_at | timestamptz | |

`session`:

| Column | Type | Notes |
|---|---|---|
| id | text, PK | 32-byte random |
| user_id | int, FK | |
| expires_at | timestamptz | |
| ip | inet | |
| user_agent | text | |
| revoked_at | timestamptz | Nullable |
| mfa_method | text | Nullable; hook for passkeys Phase 2 |

Sessions are server-side (Postgres), not JWT. Cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, path-scoped.

**Three auth flows.**

1. **Admin login** (`/admin`) — email + password → if user has MFA, prompt TOTP → issue session. MFA required for `owner`, optional for `manager`. Rate-limit: 5 fails per IP per 15 min.
2. **POS cashier login** (`/pos`) — pick name from list → 4–6 digit PIN → session. PINs only work from LAN IP range (defence-in-depth). 5 failed PINs → 5 min lock.
3. **Cashier switch** — mid-shift button. Current session ends, new cashier enters PIN. `pos_transaction.cashier_user_id` is stamped from the *active* session at `finish_transaction` time.

**Roles.**

- `owner` — everything including user management and fiscal settings.
- `manager` — everything except user management and fiscal settings (TSE config, VAT rates).
- `cashier` — POS only. Ring sales, Storno *own last* transaction within 15 minutes, open drawer for logged paid-ins/paid-outs, close day. No aggregate reports, no product edits, no other-cashier data.

**Audit log.** One `audit_event` table, append-only. Captures: logins (success + failure), logouts, role changes, product price changes, TSE-settings changes, manual inventory adjustments, Stornos, Kassenbuch entries, DSFinV-K exports. Same immutability triggers as fiscal tables. 10-year retention for fiscal-adjacent events, 2 years for others.

**Session timeouts.**

- Admin: 8 h idle, 24 h absolute max.
- POS: no idle timeout during shift; ended on explicit switch or day close.
- Owner has "log everyone out" action for incident response.

**Password rules.** Min 12 chars, rejected against HIBP k-anonymity API (local offline fallback). No periodic rotation.

**Bootstrap.** First-run `/setup` endpoint creates the first `owner` from an env-var password, then disables itself permanently (gated on Alembic-managed `first_run_completed_at`).

**Route-level enforcement.** Three FastAPI dependencies: `require_owner`, `require_manager_or_above`, `require_any_staff`. Existing admin routes → `require_manager_or_above`; POS sale routes → `require_any_staff`; fiscal exports → `require_owner`. Static `/api/uploads` stays public.

**Deferred.** SSO/SAML, magic-link, passkeys (hook in `session.mfa_method`), customer accounts.

---

## 5. Receipt printing

**Driver.** `python-escpos` direct USB, no CUPS. No spooler = no stuck-queue incidents.

**Service — `ReceiptPrinter`.** Single method `print_receipt(pos_transaction_id)`. Loads transaction + lines + TSE signature, renders via `ReceiptBuilder`, writes bytes, checks ESC/POS status byte (paper, cover, cutter), returns success/failure.

**Paper-out / offline.** Sale never fails due to printer — TSE signature already exists, sale is legally complete. POS UI shows red banner, buffers receipt, offers "Beleg erneut drucken" after resolution. Offer to print is logged in `audit_event` to satisfy Belegausgabepflicht regardless of outcome.

**Digital receipt.** Deferred; hook: existing `ReceiptBuilder` → weasyprint PDF → SMTP email. Triggered by an "Email receipt" UI button.

**Layout — 80 mm thermal.**

```
       MERCHANT NAME
       Street 1, 12345 Berlin
       St-Nr: 12/345/67890
       USt-IdNr: DE123456789
─────────────────────────────
Datum:  18.04.2026  14:23
Beleg-Nr: 2026-000847
Kasse:  KASSE-01
Bediener: Anna M.
─────────────────────────────
Äpfel Gala
  0,452 kg × 2,49 €/kg     1,13 A
Milch 1L                   1,29 A
Brötchen 6 Stk             1,80 A
Rotwein 0,75L              8,99 B
─────────────────────────────
ZWISCHENSUMME             13,21 €
Rabatt 10%                -1,32 €
─────────────────────────────
GESAMTSUMME               11,89 €

  Netto   USt   Brutto
A  7%    0,27   4,07  3,80
B 19%    1,44   9,01  7,57

Bezahlt mit:
  Girocard                 11,89 €
  (Terminal: 67891234, Trace: 001234)

─────────────────────────────
TSE-Signatur
Seriennr: abc123...
Sig-Zähler: 4728
Start: 2026-04-18T14:23:12.041Z
Ende:  2026-04-18T14:23:41.892Z
Typ:   Kassenbeleg-V1
Sig:   MEUCIQD...AgE=

     Vielen Dank für Ihren
           Einkauf!
─────────────────────────────
[QR code linking to digital copy]
```

Every field mandated by KassenSichV §6 or GoBD. A/B codes map to VAT rates; VAT breakdown reconciles to line-level totals to the cent.

**Z-Report.** Separate renderer `ZReportBuilder`. Shows shift open/close, cashier(s), transaction count, sales by VAT rate (net/VAT/gross), sales by payment method, expected vs. counted cash, TSE signature counter start→end, paid-ins/paid-outs summary, Kassendifferenz if any.

**POS health indicator.** Top bar shows four dots (DB / TSE / Printer / Terminal) polled every 30 s. Red dot + toast on failure.

---

## 6. Security baseline (minimal)

**TLS on LAN.** nginx serves self-signed certs for `pos.local`, `admin.local`, `store.local`. Root CA installed once on tablet + admin laptop so browsers trust without warnings. Without this, PINs and passwords cross the LAN in plaintext.

**CORS.** Replace `allow_origins=["*"]` with exactly the three real origins. Credentials allowed, methods restricted per route. Wildcard CORS with credentials is disallowed by browsers once cookie sessions are in place.

**No internet exposure.** NUC accepts no inbound connections from the public internet. No port-forwarding, no DDNS. Outbound only to: fiskaly, NTP, Hetzner Storage Box, Sentry (if enabled). Remote admin is Phase 2 via Tailscale.

**Secrets.** `.env` file on NUC, `chmod 600`, referenced via docker-compose `env_file:`. Required: `DB_PASSWORD`, `FISKALY_API_KEY`, `FISKALY_API_SECRET`, `FISKALY_TSS_ID`, `SESSION_SECRET_KEY`, `BACKUP_ENCRYPTION_KEY`. Secrets never logged, never in error responses. Logger has redaction filter for keys matching `/pass|secret|token|key/i`.

**Login rate-limit.** Postgres-backed counter on `/auth/login` and the POS PIN endpoint. 5 fails → temp lockout (5 min PIN, 15 min admin). ~20 lines of code; blocks trivial brute-force.

**Postgres.** Stays on private docker network, no port published. `DB_PASSWORD` long-random.

**Password + PIN hashing.** argon2id everywhere.

**Deferred to Phase 2:** CSP and full security-header set, CSRF double-submit middleware, per-endpoint rate limits, Dependabot, image upload re-encoding, egress firewall, Tailscale, extended log redaction, GDPR erasure flow.

**Phase 2 trigger:** before online channel, before any non-LAN access, or before ~10k transactions/month.

---

## 7. Backups (minimal)

- **Nightly `pg_dump -Fc` to local disk**, cron at 03:00 from a sidecar container. Also a `.sql` plain-format companion dump (forward-compatibility safety net).
- **Off-site copy via restic** to Hetzner Storage Box (~€3/mo, EU). Encrypted with passphrase from `BACKUP_ENCRYPTION_KEY`. Passphrase also written down in the owner's physical safe — if the NUC dies and the passphrase dies with it, backups are useless.
- **DSFinV-K auto-export at end-of-day** into `/fiscal-archive/YYYY/MM/DD.zip`, included in the restic snapshot. Even if Postgres restore is ever problematic, the Finanzamt-facing archive is always directly readable as a standalone ZIP.
- **One-page restore runbook** in the repo + printed copy at the shop. Covers: "NUC dead, here's how to restore onto a fresh Ubuntu install."
- **Pre-go-live restore drill** — run the restore procedure once end-to-end before real customers. Backups that have never been restored are a coin flip.

**Deferred to Phase 2:** WAL archiving / PITR, cold-spare NUC swap automation, USB-drive rotation, quarterly scheduled drills, automated backup monitoring, annual GoBD rehydration procedure.

---

## 8. Observability & operations

**Logs.** Structured JSON to stdout → journald. `docker compose logs -f api` for day-to-day. 500 MB on-disk cap.

**Error reporting.** Sentry free tier. Backend exceptions + frontend unhandled errors. Owner emailed on new issue types.

**Health endpoints.**

- `/api/health` (existing)
- `/api/health/fiskaly` — ping + last successful signature timestamp
- `/api/health/printer` — ESC/POS status byte
- `/api/health/terminal` — ZVT diagnosis command
- `/api/health/db` — simple query

POS top bar consumes these — four small status dots so the cashier sees a problem before a customer is standing there.

**Uptime ping.** `healthchecks.io` free tier. Cron pings every 5 min; two missed → owner emailed. Catches "NUC crashed overnight" before opening hour.

**Deployment.** `./deploy.sh` script on NUC: `git pull`, `docker compose pull`, `docker compose up -d`, run pending Alembic migrations, restart. ~30 s downtime — always run before opening hour. Rollback: `git checkout <prev-sha> && docker compose up -d`. Documented in runbook.

**Deferred to Phase 2:** Prometheus/Grafana, log aggregation (Loki/ELK), distributed tracing, business-metric alerts (e.g., no sales in 2 h), per-cashier performance reports.

---

## 9. Testing & go-live checklist

### Automated tests

- **Unit tests** on new services (`FiscalService`, `PaymentTerminalService`, `ReceiptPrinter`, `ReceiptBuilder`, `ZReportBuilder`, `KassenbuchService`, auth/role dependencies).
- **Integration tests against fiskaly sandbox** — full day scenario: open, 20 varied sales including weighed + Storno + mixed-payment, close with Z-report. Verify signature roundtrip.
- **ZVT mock-terminal tests** — `python-zvt`'s test harness. Cover: approve, decline, reversal, partial-auth, terminal-offline. Real terminal only touched during manual acceptance.
- **Receipt golden-file tests** — render fixture `pos_transaction` through `ReceiptBuilder`, byte-compare against committed ESC/POS golden.
- **DSFinV-K export validation** — community `dsfinvk-validator` in CI against the BMF schema. Build fails on malformed export.
- **Migration tests** — every Alembic migration up + down against fresh Postgres in CI.
- **Immutability tests** — attempted UPDATE/DELETE on fiscal rows must be rejected by triggers.

### Manual acceptance — real hardware, before go-live

Cashier + developer + Steuerberater present. Written checklist:

1. Fixed-price cash sale with change. Verify receipt fields, drawer opened, Z-report shows sale.
2. Weighed-produce sale (0.452 kg apples). Verify kg display and receipt.
3. Mixed-payment sale (€10 cash + €15 girocard). Verify split on receipt and in `payment_breakdown`.
4. Card declined → re-tap approved. Verify only approved transaction signed.
5. Storno last sale. Verify negative-qty transaction, both in DSFinV-K export.
6. Printer USB unplugged mid-sale. Verify sale completes, receipt buffers, reprint works after reconnect.
7. NUC network cable unplugged. Verify sales still work (fiskaly fallback), deferred signing runs on reconnect.
8. Full shift simulation: €150 opening float, ~15 sales, close. Cash count matches, Z-report prints, DSFinV-K is valid.
9. Steuerberater opens the DSFinV-K export in audit software (IDEA / WinIDEA) and confirms it's readable and complete.
10. Restore drill: wipe spare NUC, restore from restic, run a test sale. DB + uploads + fiscal archive all present.

### Calendar go-live checklist

- **Finanzamt Kasse registration** (§146a AO via Mitteilungsverfahren — ELSTER once live; letter to local Finanzamt until then). Deadline: within 1 month of deployment.
- Retention contract with fiskaly confirmed (they hold signatures 10 years — part of their paid plan, verify active).
- Steuerberater sign-off letter retained (useful if audited in year 3).
- Cashier trained on all 10 manual test flows.
- Backup restore drill completed and dated.
- Emergency contact list on the printed runbook: fiskaly support, terminal support, developer, Steuerberater, ISP.
- First week: daily check-in between friend and developer to catch anything automated checks missed.

**"Done" = all 10 automated test categories green + all 10 manual tests pass with Steuerberater present + restore drill passed + Finanzamt registration submitted + cashier can run a full shift unaided. Then and only then, real customers.**
