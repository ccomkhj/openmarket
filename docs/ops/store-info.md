# Store Info (Merchant Identity)

These values are printed on every receipt (§14 UStG requirement in DE)
and shown on the **Admin → Settings** page. They live in `.env` on the
server, not in the database, so a single edit + restart updates
everything: receipts, invoices, online shop imprint.

## Fields

| .env variable          | Example                            | Used in                         |
|------------------------|------------------------------------|---------------------------------|
| `MERCHANT_NAME`        | `My Market GmbH`                   | receipt header, online shop     |
| `MERCHANT_ADDRESS`     | `Musterstr. 1, 12345 Musterstadt`  | receipt header, online imprint  |
| `MERCHANT_TAX_ID`      | `123/456/78901` (Steuernummer)     | receipt, Z-report               |
| `MERCHANT_VAT_ID`      | `DE123456789` (USt-IdNr.)          | receipt (`USt-IdNr:` line)      |
| `MERCHANT_REGISTER_ID` | `KASSE-01`                         | receipt, DSFinV-K export        |

## Changing values

1. SSH to the host.
2. `nano .env` — edit the MERCHANT_* lines.
3. `docker compose restart api` — takes ~5 seconds.
4. Reload **Admin → Settings** and confirm the **Store Info** panel
   reflects the change.
5. Print a test receipt (ring up a 1-cent test sale, then Storno) to
   confirm the header looks right.

## Why not editable in the UI?

Because these affect fiscal records and can't be accidentally changed by
a cashier. Root/SSH access is the safety interlock.
