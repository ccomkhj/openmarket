# OpenMarket UX Review — Customer Perspective

**Reviewer:** Regular customer who values user-friendly experience
**Date:** 2026-04-03
**UX Score: 3 / 10**

---

## Overall Impression

This feels like a developer's internal prototype, not a store that's ready for real customers. The bones are functional — I can browse, add to cart, and place an order — but every step of the journey has friction that would make me abandon the site and go back to Coupang or GMarket within 60 seconds. The design lacks virtually all modern e-commerce conventions that customers now take for granted.

---

## What Works Well

- **Search is instant and reactive** — results update live on every keystroke without needing to press Enter.
- **Cart quantity adjustment works correctly** — automatically removes the item when quantity drops to 0.
- **Duplicate-add is handled** — increments quantity instead of adding a duplicate row.
- **Order confirmation state** — after a successful order, shows a clean confirmation with a direct link to order tracking.
- **Discount code support exists** — most small stores don't even have this.

---

## Pain Points

### Critical

- **No product images, ever.** The API returns `"images": []` and the product card renders nothing but a title and product type. A customer cannot confidently buy "Whole Milk 1L" from a plain text card. This alone would cause most users to leave immediately.

- **No price shown on the product listing cards.** Price is only visible *after* clicking to open the side panel. For any e-commerce store, price is one of the top 3 decision factors. Hiding it behind a click is a conversion killer.

- **No cart item count visible in the nav.** Plain `Cart` link with no badge showing how many items are in the cart. Users constantly need to ask "did that item get added?"

- **Order lookup fetches ALL orders and searches client-side.** This is a privacy and scalability disaster. A real customer could see other customers' order numbers in DevTools. It also breaks as the order count grows.

- **`placeOrder` has no validation beyond 3 fields.** `city` and `zip` are required but not guarded. A user who leaves `zip` blank will hit a confusing API error.

### Major

- **No loading states anywhere.** On a slow connection, the user sees a blank white grid for 1–3 seconds with no explanation. Clicking a product card has zero feedback while the API call is in flight.

- **Product detail is a side panel, not a page.** On mobile, a 300px panel on a 375px phone screen takes over entirely. No URL change means no shareable product links.

- **No payment information collected at checkout.** No indication of how payment works. A customer will be confused when an order goes through without entering a card.

- **"Place Order" button has no loading/disabled state during submission.** A user who clicks twice could create duplicate orders.

- **Error messages are generic.** Raw API error text with no context.

- **WebSocket is wired up but does nothing.** Inventory updates arrive silently and are discarded. If stock runs out, the customer has no idea.

- **No category/filter browsing.** The only discovery mechanism is a text search box.

### Minor

- **Product description is empty for all products.**
- **`compare_at_price` is in the API but never shown.** Missed opportunity for sale badging.
- **No "continue shopping" link or confirmation toast after adding to cart.**
- **No empty state when search returns 0 results.**
- **Inline styles everywhere, no dark mode, no responsive breakpoints.**
- **No favicon, page title, or meta tags.**

---

## Specific Suggestions

1. **Add a cart item count badge in the nav** — Use `useCart().items.reduce((sum, i) => sum + i.quantity, 0)`. One line of logic, high impact.

2. **Show price on the product grid card** — Consider including `min_price` in the list API response, or show "from $X.XX".

3. **Add loading states** — Show a spinner or skeleton grid while products load. Disable product cards while detail is resolving.

4. **Convert product detail panel into a proper route** — Add `/product/:id` route. Fixes mobile layout, enables URL sharing, supports browser history.

5. **Fix order lookup to use a server-side filter** — Pass order number as a filter parameter instead of fetching all orders.

6. **Add a submitting state to Place Order** — Disable button during submission and add `city`/`zip` to the disabled condition.

7. **Implement the WebSocket inventory handler** — At minimum re-fetch products or show "Out of Stock" badges in real time.

8. **Add payment method explanation** — If cash-on-delivery, add a visible note. If card payments coming, add a placeholder section.
