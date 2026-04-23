# Customer on Orders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Show the customer's name on the Orders list and let staff search by customer name, so a phone call about "my order" can be handled without a database.

**Architecture:** Extend `OrderListOut` with optional `customer_name` and `customer_email`. Eager-load the `customer` relationship in `list_orders`, map on the way out. Extend the search filter to match customer first/last name too. Frontend type + column + placeholder text.

**Tech Stack:** FastAPI, SQLAlchemy, React.

---

### Task 1: Schema — add customer fields

**Files:**
- Modify: `backend/app/schemas/order.py`

- [ ] **Step 1: Extend OrderListOut**

Replace the `OrderListOut` class with:

```python
class OrderListOut(BaseModel):
    id: int
    order_number: str
    source: str
    fulfillment_status: str
    total_price: Decimal
    created_at: datetime
    customer_name: str | None = None
    customer_email: str | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/order.py
git commit -m "feat(schemas): customer on OrderListOut"
```

---

### Task 2: API — populate & filter

**Files:**
- Modify: `backend/app/api/orders.py`

- [ ] **Step 1: Update list_orders**

Replace the body of `list_orders` with:

```python
    from app.models.customer import Customer
    from sqlalchemy import or_

    query = select(Order).options(selectinload(Order.customer))
    if source:
        query = query.where(Order.source == source)
    if fulfillment_status:
        query = query.where(Order.fulfillment_status == fulfillment_status)
    if search:
        like = f"%{search}%"
        query = query.outerjoin(Customer, Order.customer_id == Customer.id).where(
            or_(
                Order.order_number.ilike(like),
                Customer.first_name.ilike(like),
                Customer.last_name.ilike(like),
                Customer.email.ilike(like),
            )
        )
    if date_from:
        query = query.where(Order.created_at >= date_from)
    if date_to:
        query = query.where(Order.created_at <= date_to)
    query = query.order_by(Order.created_at.desc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()

    out: list[OrderListOut] = []
    for o in orders:
        c = o.customer
        name = f"{c.first_name} {c.last_name}".strip() if c else None
        out.append(OrderListOut(
            id=o.id, order_number=o.order_number, source=o.source,
            fulfillment_status=o.fulfillment_status, total_price=o.total_price,
            created_at=o.created_at,
            customer_name=name or None,
            customer_email=(c.email if c else None),
        ))
    return out
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/orders.py
git commit -m "feat(api): orders list includes customer name and searches by it"
```

---

### Task 3: Frontend type + column

**Files:**
- Modify: `frontend/packages/shared/src/types.ts`
- Modify: `frontend/packages/admin/src/pages/OrdersPage.tsx`

- [ ] **Step 1: Extend OrderListItem**

In `types.ts` replace OrderListItem:

```typescript
export interface OrderListItem {
  id: number;
  order_number: string;
  source: string;
  fulfillment_status: string;
  total_price: string;
  created_at: string;
  customer_name?: string | null;
  customer_email?: string | null;
}
```

- [ ] **Step 2: Add Customer column to table**

In `OrdersPage.tsx`:

a) Table header — insert a `Customer` `<th>` between `Source` and `Total`:

```tsx
                <th style={{ padding: "10px 16px" }}>Customer</th>
```

b) Table row — insert matching cell between the `Source` badge cell and the `Total` cell:

```tsx
                    <td style={{ padding: "10px 16px", color: colors.textSecondary }}>
                      {o.customer_name || "—"}
                    </td>
```

c) Update the `colSpan` on the expanded row (currently `colSpan={5}`) to `6`.

d) Update the search input placeholder from `Search order #...` to `Search order # or customer...`.

e) Update `handleExport` to include a Customer column:

```tsx
      ["Order #", "Source", "Customer", "Total", "Date", "Status"],
      orders.map((o) => [o.order_number, o.source, o.customer_name ?? "", `$${o.total_price}`, new Date(o.created_at).toLocaleDateString(), o.fulfillment_status]),
```

- [ ] **Step 3: Build**

Run: `cd frontend && pnpm -F @openmarket/admin build`

- [ ] **Step 4: Commit**

```bash
git add frontend/packages/shared/src/types.ts frontend/packages/admin/src/pages/OrdersPage.tsx
git commit -m "feat(admin): customer column on Orders page + search by name"
```

---

## Self-review

- Spec coverage: schema (T1), API + filter (T2), UI column + search placeholder (T3).
- No placeholders.
- Type consistency: `customer_name?: string | null` matches `customer_name: str | None` in Pydantic.
