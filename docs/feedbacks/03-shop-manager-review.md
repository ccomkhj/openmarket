# OpenMarket Admin & POS — Shop Manager Review

**Reviewer:** Busy shop manager who wants to manage with least effort
**Date:** 2026-04-03
**Manager Score: 2 / 10**

---

## Overall Impression

This looks like a developer's prototype, not a tool ready for a real shop. The bones are there — products, inventory, orders, a POS screen — but every critical daily task requires too many clicks, too much waiting, and too much guesswork. Compared to Square or even a basic Shopify setup, this would slow my staff down and cost me money on day one.

---

## What Works Well

- **Real-time inventory sync via WebSocket** — when a sale happens, the stock count updates live on the admin screen. Genuinely useful.
- **Low-stock warning is visible** — the red "(LOW)" label on variants is exactly what I need at a glance.
- **Barcode scan auto-focuses on load** — the POS barcode field is focused when the screen opens. That's what a real scanner needs.
- **Unfulfilled / Fulfilled tab split on orders** — simple, obvious, I can immediately see what needs action.
- **"Complete Sale" button is large and green** — the most important POS button is prominent. Staff won't miss it.
- **Search fallback on POS** — if a barcode doesn't scan, staff can type a product name.

---

## Pain Points

### DEALBREAKERS

- **Barcode scanning is broken by design.** When a barcode is scanned, the code fetches ALL active products, then fetches each product one by one to find a matching barcode. With 500 products, that's 500+ API calls per scan. A cashier scanning 50 items will bring the server to its knees. Square resolves a barcode in one API call. Completely unusable in a real store.

- **No way to add or edit products.** The entire Products page is read-only. I cannot add a new product, change a price, update a barcode, or fix a typo. I would have to go directly into a database. Dealbreaker on day one.

- **No payment processing at the POS.** "Complete Sale" creates an order, but there is no payment step. No cash, no card, no change calculation. The system doesn't know if the customer actually paid.

- **No way to cancel or void a sale.** If a cashier rings up the wrong item and clicks "Complete Sale," there is no refund button, no void, no undo anywhere in the UI.

### MAJOR

- **No dashboard or summary screen.** I open the app and have no idea how today is going. No total revenue, no number of orders, no items sold. I would have to manually add up orders in my head. A spreadsheet beats this.

- **Fulfilling an order requires 2 clicks plus a page load.** Click the order row, wait for API call, then click "Mark as Fulfilled." No "Fulfill All" or bulk action. 30 online orders = 90 clicks.

- **Inventory adjustment is one unit at a time.** The +1 / -1 / +10 buttons are fine for corrections, but receiving a delivery of 200 units across 15 products means clicking +10 twenty times per product. No "set stock to X" input field.

- **No search or filter on the Products page.** With 200 products, I have to scroll the entire list to find "Organic Eggs." No search bar, no filter by category, no sorting.

- **Stock level is hidden until you click.** Inventory numbers are inside collapsed rows. I cannot see at a glance which products are low. I have to click every product one by one.

- **Orders list shows no customer name.** Only order number, source, total, date, and status. If a customer calls about their order, I have nothing to search by.

### MINOR

- **Quantity cannot be edited in POS cart.** If a customer wants 3 of the same item, the cashier must scan it 3 times. No quantity field.
- **"X" button to remove POS items** — a single misclick removes an entire item with no confirmation.
- **Success message on POS disappears after 3 seconds** — no receipt, no order number shown, no confirmation reference.
- **The UI has no real styling.** Raw HTML tables with inline styles. Looks unprofessional. Staff would not trust it.

---

## Missing Features I Need on Day 1

- **Add / Edit / Delete products and prices** — cannot run a shop without this
- **Payment processing** or at minimum cash/card tender tracking
- **Refunds and voids** — mistakes happen every hour in a real store
- **A daily summary dashboard** — today's revenue, transactions, top-selling items
- **Inventory bulk entry / CSV import** — receiving stock deliveries fast
- **"Set stock to X" input** — instead of clicking +10 repeatedly
- **A low-stock report view** — one page showing only items below threshold
- **Customer information on orders** — name, email, phone
- **Receipt printing or emailing**
- **Tax calculation** — total shown is pre-tax with no tax line
- **Discount / coupon on POS** — percentage-off field at point of sale
- **Multi-location support in UI** — the API supports `location_id` but UI hardcodes 1

---

## Specific Suggestions

1. **Fix barcode lookup immediately.** Add a `/api/products?barcode=<value>` endpoint. One API call per scan. The current approach is a server-killer.

2. **Add inline "Edit" mode on product rows.** Clicking a product should show editable fields for price, barcode, and SKU directly in the table.

3. **Add a "Set Stock" input next to +/- buttons.** A text box where I type 150 and press Enter. Done.

4. **Add a Dashboard page as the default route.** Show: today's revenue, number of sales, unfulfilled orders, low-stock items. Four numbers = my morning briefing.

5. **Add "Fulfill All" button** at the top of the unfulfilled orders tab, or checkboxes for bulk fulfillment.

6. **Add quantity field to POS cart items.** Let cashiers type a number instead of scanning repeatedly.

7. **Add "Void Sale" / Cancel button on POS.** One click to clear the cart with confirmation.

8. **Add a tender/payment step.** Even just "Cash / Card" buttons and "Change due: $X.XX" display.

9. **Add low-stock filter to Products page.** A toggle showing only variants below threshold.

10. **Add searchable, sortable product list.** A search bar at the top of Products page — 30-minute fix saving hours per week.

---

**Bottom line:** I would not use this to run my shop today. The core loop — scan item, take payment, update stock, record sale — is only half-implemented. With 4-6 weeks of focused work on the dealbreakers, this could reach a 6 or 7. Right now, a Google Sheet and a Square reader would outperform it.
