# First-Run Bootstrap

When the stack comes up on a fresh NUC, the database has zero users. The
admin UI probes `GET /api/auth/bootstrap-status` and auto-routes to the
Setup form when `setup_required: true`. After the first owner is created,
the endpoint returns `setup_required: false` and the admin shows the normal
Login form from then on.

## Steps

1. Bring up the stack: `docker compose up -d`.
2. Open `https://admin.local` on the admin laptop. You should see the
   Setup form (no URL flag needed).
3. Enter a strong passphrase (min 12 chars, validated against HIBP).
4. Submit. You are logged in as owner and land in the admin dashboard.
5. Go to **Security** → **Enroll MFA**. Scan the QR code into Authy /
   1Password / Aegis and verify the first 6-digit code. MFA is now required
   for this owner on subsequent logins.
6. Go to **Users** → **New user**. Create the rest of the staff:
   - One or more **managers** (optional MFA, strongly recommended).
   - One or more **cashiers** — no email, 4-6 digit PIN instead.
7. Create a second owner-role user as a break-glass backup. Store its
   password in the physical safe. Never use it; it exists so a lost-device
   MFA lockout never becomes "store cannot operate."

## What not to do

- Never commit `.env` to the repo.
- Never share the session cookie.
- Never disable HIBP in production (`hibp_enabled=False`) — it's there
  precisely to catch a weak owner passphrase.

## After updating nginx.conf

Whenever `nginx.conf` changes, either restart the nginx container
(`docker compose restart nginx`) or reload in-place
(`docker compose exec nginx nginx -s reload`). The running container reads
the file via a bind mount, so edits in the repo take effect after the
reload — no rebuild required.
