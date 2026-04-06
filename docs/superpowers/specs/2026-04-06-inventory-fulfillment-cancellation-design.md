# Inventory Audit Trail, Partial Fulfillment & Order Cancellation

## Overview

Three interconnected features for the OpenMarket order/inventory lifecycle:

1. **Inventory Audit Trail** - Log every stock change with source, reason, and reference
2. **Partial Fulfillment** - Ship orders in multiple shipments with per-item tracking
3. **Order Cancellation** - Cancel unfulfilled orders with automatic inventory restoration

All three features share inventory restoration/logging patterns and are designed together to ensure consistency.

---

## 1. Inventory Audit Trail

### Model: `InventoryLog`

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `inventory_item_id` | FK → inventory_items | Which stock item changed |
| `location_id` | Integer | Which location |
| `previous_quantity` | Integer | Stock level before change |
| `new_quantity` | Integer | Stock level after change |
| `delta` | Integer | Change amount (+/-) |
| `reason` | String | One of: `manual_set`, `manual_adjust`, `order`, `return`, `cancellation` |
| `reference` | String | Free text, e.g. `"ORD-20260406-1001"`, `"Return #5"` |
| `created_at` | DateTime(tz) | server_default=now() |

Indexes: `inventory_item_id`, `created_at`.

### Where logs are created

| Operation | Reason | Reference |
|---|---|---|
| `inventory.set_inventory()` | `manual_set` | empty |
| `inventory.adjust_inventory()` | `manual_adjust` | empty |
| `order.create_order()` | `order` | order number |
| `returns.create_return()` | `return` | `"Return for {order_number}"` |
| `order.cancel_order()` | `cancellation` | order number |

### Logging helper

A shared `log_inventory_change()` function in the inventory service that creates the log entry. All services call this instead of duplicating the logic.

### API

- `GET /api/inventory-logs?inventory_item_id={id}` - Returns logs for a specific inventory item, ordered by `created_at` desc. Optional `limit` (default 50) and `offset` params.

### Admin UI

In `ProductsInventoryPage`, when a product row is expanded and a variant is shown, add a "History" button next to the stock controls. Clicking it shows a list of recent log entries (timestamp, delta, reason, reference) below the variant row.

---

## 2. Partial Fulfillment

### Model changes

**`Fulfillment` - add columns:**

| Column | Type | Description |
|---|---|---|
| `tracking_number` | String, nullable | Shipping tracking number |
| `carrier` | String, nullable | Carrier name (UPS, FedEx, USPS, etc.) |

**New model: `FulfillmentLineItem`**

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | |
| `fulfillment_id` | FK → fulfillments (CASCADE) | |
| `line_item_id` | FK → line_items | |
| `quantity` | Integer | Quantity shipped in this fulfillment |

Index: `fulfillment_id`.

Relationship: `Fulfillment.line_items` → list of `FulfillmentLineItem`.

### Order fulfillment status logic

When a fulfillment is created, recalculate the order's `fulfillment_status`:

1. For each line item, sum the quantities across all fulfillments
2. If all line items are fully covered → `"fulfilled"`
3. If at least one fulfillment exists but not all covered → `"partially_fulfilled"`
4. If no fulfillments → `"unfulfilled"`

This is computed in a helper function `recalculate_fulfillment_status(order)` called after every fulfillment creation.

### API changes

**`POST /api/orders/{order_id}/fulfillments`** - Updated request body:

```json
{
  "tracking_number": "1Z999...",
  "carrier": "UPS",
  "line_items": [
    {"line_item_id": 1, "quantity": 2},
    {"line_item_id": 3, "quantity": 1}
  ]
}
```

Validation:
- Each `line_item_id` must belong to the order
- Quantity must not exceed remaining unfulfilled quantity for that line item
- Order must not be `"cancelled"`

Response includes the fulfillment with its line items.

**`GET /api/orders/{order_id}`** - Response now includes fulfillments with their line items, tracking number, and carrier.

### Schema changes

**`FulfillmentCreate`** - Add optional `tracking_number`, `carrier`, `line_items` fields. All optional for backwards compatibility (POS creates fulfillments with just `{status: "delivered"}`). When `line_items` is omitted, the fulfillment covers all remaining unfulfilled quantities (preserving current behavior).

**`FulfillmentOut`** - Add `tracking_number`, `carrier`, `line_items` fields.

**`FulfillmentLineItemOut`** - New schema: `id`, `line_item_id`, `quantity`, `title` (from the line item).

**`OrderOut`** - Add `fulfillments: list[FulfillmentOut]` field.

### Admin UI

In the expanded order detail on `OrdersPage`:
- Show fulfillment history: each fulfillment with its items, tracking number, carrier, date
- Show unfulfilled items with checkboxes
- "Create Shipment" button (replaces "Mark as Fulfilled") opens a form:
  - Checkboxes for items to include (pre-checked with remaining quantities)
  - Quantity inputs for each checked item
  - Tracking number input
  - Carrier dropdown (UPS, FedEx, USPS, DHL, Other)
  - Submit creates the fulfillment

---

## 3. Order Cancellation

### Model changes

Add `"cancelled"` as a valid value for `Order.fulfillment_status`. No new columns needed.

The existing filter tabs in admin already use `fulfillment_status`, so adding a "Cancelled" tab is straightforward.

### Cancellation rules

- Only orders with `fulfillment_status = "unfulfilled"` can be cancelled
- Partially fulfilled or fulfilled orders cannot be cancelled (use returns)
- POS orders (auto-fulfilled) cannot be cancelled

### Service: `cancel_order()`

Located in `backend/app/services/order.py`:

1. Load order with line items
2. Validate `fulfillment_status == "unfulfilled"`
3. For each line item:
   - Find the inventory item for the variant
   - Restore quantity: `UPDATE inventory_levels SET available = available + quantity`
   - Log the restoration via `log_inventory_change()` with reason `"cancellation"`, reference = order number
   - Broadcast WebSocket inventory update
4. Set `order.fulfillment_status = "cancelled"`
5. Commit and return the order

### API

- `POST /api/orders/{order_id}/cancel` - Cancels the order. Returns 409 if order is not unfulfilled. Returns the updated order.

### Admin UI

- Expanded order detail: show "Cancel Order" button (danger variant) for unfulfilled orders
- ConfirmDialog before executing: "Cancel this order? Inventory will be restored for all items."
- Orders page: add "Cancelled" tab alongside Unfulfilled/Fulfilled
- Cancelled orders display with a distinct badge style

### Store UI

- `OrderStatusPage`: Show "Cancelled" status badge when order is cancelled

---

## Shared patterns

### Inventory restoration

Both `cancel_order()` and `create_return()` restore inventory. Extract the common pattern:

```
async def restore_line_item_inventory(db, line_item, quantity, reason, reference):
    # Find inventory item → update level → log → broadcast
```

This avoids duplicating the restoration logic across returns and cancellation services.

### WebSocket broadcast

All inventory changes already broadcast via the existing `manager.broadcast()`. The audit trail adds logging but doesn't change the broadcast pattern.

---

## Migration notes

Three new/modified tables:
- **New:** `inventory_logs` table
- **New:** `fulfillment_line_items` table
- **Modified:** `fulfillments` table (add `tracking_number`, `carrier` columns)

Since the project uses `Base.metadata.create_all` and the `alembic/versions/` directory is empty, new tables will be created automatically in tests. For the production DB, either run `create_all` or create an Alembic migration.
