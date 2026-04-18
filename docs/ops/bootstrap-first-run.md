# First-Run Bootstrap

Once the stack is up on a fresh NUC, the database has zero users. The admin
UI detects this and routes to `/setup`. Only the very first call to
`POST /api/auth/setup` succeeds — subsequent calls return 409 even if the
first owner is deleted, because the guard is "any user exists".

## Steps

1. Bring up the stack: `docker compose up -d`.
2. Open `https://admin.local` on the admin laptop. You should see the Setup form.
3. Enter a strong passphrase (min 12 chars, will be checked against HIBP).
4. Submit. You are logged in as owner and bounced to the admin dashboard.
5. Under **Settings → Security**, enroll TOTP MFA. Scan the QR code into
   Authy / 1Password / Aegis. Verify the first 6-digit code. MFA is now required
   for this account on subsequent logins.
6. Under **Users**, create the rest of the staff:
   - Managers (optional MFA, recommended)
   - Cashiers (no email, 4-6 digit PIN only)
7. Create a second owner-role user as a break-glass backup. Store its password
   in the physical safe. Never uses it — it exists so a lost-device MFA flow
   never becomes "store cannot operate."

## What not to do

- Never commit `.env` to the repo.
- Never share the session cookie.
- Never disable HIBP in production (`hibp_enabled=False`) — it's there
  precisely to catch the owner using a weak passphrase.

## After updating nginx.conf

Whenever `nginx.conf` changes, either restart the nginx container
(`docker compose restart nginx`) or reload in-place
(`docker compose exec nginx nginx -s reload`). The running container reads
the file via a bind mount, so edits in the repo take effect after the
reload — no rebuild required.
