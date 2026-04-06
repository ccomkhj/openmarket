# OpenMarket — Design Spec

A unified inventory management system for a single supermarket, connecting in-store POS and an online web store through a shared backend.

## Goals

- Single source of truth for product catalog and inventory across online and offline channels
- Real-time stock sync: POS sale instantly reflected in web store, and vice versa
- Self-hosted on the shop's own server via Docker Compose

## Non-Goals (for MVP)

- Payment processing (handled externally)
- Customer accounts / authentication
- Multi-location support (data model supports it, but UI is single-location)
- Pickup orders (delivery only)
- Discount management UI (manage via API/DB)
- Analytics dashboard

## Tech Stack

- **Backend**: Python, FastAPI, PostgreSQL, SQLAlchemy, Alembic
- **Frontend**: React, Vite, TypeScript (monorepo with shared package)
- **Real-time**: WebSocket (FastAPI native)
- **Deployment**: Docker Compose (FastAPI + PostgreSQL + Nginx)

## Project Structure

```
openmarket/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── ws/           # WebSocket manager
│   ├── alembic/          # DB migrations
│   └── requirements.txt
├── frontend/
│   ├── packages/
│   │   ├── shared/       # API client, types, common components
│   │   ├── store/        # Customer web store
│   │   ├── admin/        # Admin dashboard
│   │   └── pos/          # POS interface
│   └── package.json
├── docker-compose.yml
└── nginx.conf
```

## Data Model

### Product

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| title | string | |
| handle | string, unique | URL slug |
| description | text | |
| product_type | string | e.g. "dairy", "bakery" |
| status | enum | active / draft / archived |
| tags | array[string] | flexible filtering |
| created_at | timestamp | |
| updated_at | timestamp | |

### ProductVariant

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| product_id | int, FK | |
| title | string | e.g. "1L", "500ml" |
| sku | string | |
| barcode | string | for POS scanning |
| price | decimal | |
| compare_at_price | decimal, nullable | for showing discounts |
| position | int | sort order |

### ProductImage

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| product_id | int, FK | |
| src | string | relative path, served from local uploads directory via Nginx |
| position | int | sort order |

### Collection

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| title | string | |
| handle | string, unique | |
| collection_type | enum | manual / automated |
| rules | JSON, nullable | for automated collections |

### CollectionProduct

| Column | Type | Notes |
|--------|------|-------|
| collection_id | int, FK | |
| product_id | int, FK | |
| position | int | |

### InventoryItem

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| variant_id | int, FK, unique | |
| cost | decimal, nullable | cost price |

### InventoryLevel

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| inventory_item_id | int, FK | |
| location_id | int, FK | |
| available | int | sellable quantity |
| low_stock_threshold | int | alert threshold |

### Location

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| name | string | |
| address | string | |

### Customer

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| email | string, nullable | |
| first_name | string | |
| last_name | string | |
| phone | string | |

### CustomerAddress

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| customer_id | int, FK | |
| address1 | string | |
| city | string | |
| zip | string | |
| is_default | bool | |

### Order

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| order_number | string, unique | human-readable, e.g. #1001 |
| customer_id | int, FK, nullable | nullable for guest checkout |
| source | enum | web / pos |
| fulfillment_status | enum | unfulfilled / fulfilled |
| total_price | decimal | |
| shipping_address | JSON, nullable | snapshot, null for POS orders |
| created_at | timestamp | |

### LineItem

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| order_id | int, FK | |
| variant_id | int, FK | |
| title | string | snapshot at order time |
| quantity | int | |
| price | decimal | unit price snapshot |

### Fulfillment

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| order_id | int, FK | |
| status | enum | pending / in_transit / delivered |
| created_at | timestamp | |

### Discount

| Column | Type | Notes |
|--------|------|-------|
| id | int, PK | |
| code | string, unique | |
| discount_type | enum | percentage / fixed_amount |
| value | decimal | |
| starts_at | timestamp | |
| ends_at | timestamp | |

## API Endpoints

### Products

- `GET /api/products` — list (filter by collection, status, search)
- `GET /api/products/{id}` — detail with variants and images
- `POST /api/products` — create with variants
- `PUT /api/products/{id}` — update
- `DELETE /api/products/{id}` — archive

### Variants

- `POST /api/products/{id}/variants` — add variant
- `PUT /api/variants/{id}` — update
- `DELETE /api/variants/{id}` — remove

### Collections

- `GET /api/collections` — list
- `GET /api/collections/{id}/products` — products in collection
- `POST /api/collections` — create
- `PUT /api/collections/{id}` — update

### Inventory

- `GET /api/inventory-levels?location_id=X` — stock levels
- `POST /api/inventory-levels/set` — set absolute quantity
- `POST /api/inventory-levels/adjust` — relative adjustment (+/- delta)

### Orders

- `GET /api/orders` — list (filter by source, status)
- `GET /api/orders/{id}` — detail with line items
- `POST /api/orders` — create (web store and POS both use this)
- `PUT /api/orders/{id}` — update

### Fulfillments

- `POST /api/orders/{id}/fulfillments` — create
- `PUT /api/fulfillments/{id}` — update status

### Customers

- `GET /api/customers` — list
- `GET /api/customers/{id}` — detail with addresses and orders
- `POST /api/customers` — create

### Discounts

- `POST /api/discounts/lookup?code=X` — validate at checkout

### WebSocket

- `WS /api/ws` — real-time inventory updates
  - Message format: `{"type": "inventory_updated", "variant_id": 5, "location_id": 1, "available": 23}`

## Frontend Pages

### Web Store (3 pages)

**Shop page** — product grid with category filter sidebar and search bar. Combines homepage and collection browsing into one page.

**Cart + Checkout** — single page. Cart items on top with quantity adjustment. Guest checkout form below (name, phone, address). Discount code input.

**Order status** — lookup by order number. Shows order details and fulfillment status.

### Admin Dashboard (2 pages)

**Products & Inventory** — single table view. Products with variants, stock levels, and prices all inline-editable. Image upload, collection assignment, and inventory adjustment in the same view. Low-stock items highlighted.

**Orders & Fulfillments** — table with status tabs (unfulfilled / fulfilled). Click row to expand details and mark as fulfilled. Shows both web and POS orders.

### POS (1 page)

**Sale screen** — auto-focused barcode scan input (works with USB scanners). Type-ahead search fallback. Running list of scanned items with quantities and running total. Complete sale button creates order with `source: pos`, `fulfillment_status: fulfilled`, and auto-deducts inventory. POS orders are immediately fulfilled (no delivery step).

## Real-time Inventory Sync

1. All inventory changes go through the API (`/api/inventory-levels/adjust`)
2. API performs atomic DB update: `UPDATE inventory_level SET available = available - :qty WHERE available >= :qty`
3. If 0 rows affected → out of stock → return error
4. On success, broadcast update via WebSocket to all connected clients
5. POS and web store receive update and reflect new stock instantly

No message queue, no cache layer, no event bus. PostgreSQL is the single source of truth. WebSocket is notification only.

## Deployment (Self-hosted)

Docker Compose with three services:

- **api**: FastAPI app (Uvicorn)
- **db**: PostgreSQL
- **nginx**: serves built frontend static files + reverse proxy to API

```yaml
# Simplified docker-compose.yml
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: openmarket
      POSTGRES_USER: openmarket
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  api:
    build: ./backend
    depends_on: [db]
    environment:
      DATABASE_URL: postgresql://openmarket:${DB_PASSWORD}@db/openmarket

  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./frontend/packages/store/dist:/usr/share/nginx/html/store
      - ./frontend/packages/admin/dist:/usr/share/nginx/html/admin
      - ./frontend/packages/pos/dist:/usr/share/nginx/html/pos
    depends_on: [api]

volumes:
  pgdata:
```
