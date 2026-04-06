# OpenMarket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified inventory management system for a single supermarket with real-time stock sync between POS and web store.

**Architecture:** FastAPI backend with PostgreSQL as single source of truth. Three React SPA frontends (store, admin, POS) in a Vite monorepo sharing a common package. WebSocket broadcasts inventory changes to all connected clients. Self-hosted via Docker Compose.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, React 18, TypeScript, Vite, pnpm workspaces, Docker Compose

**Spec:** `docs/superpowers/specs/2026-04-03-openmarket-design.md`

---

## File Structure

### Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, CORS, router includes
│   ├── config.py                # Settings from env vars
│   ├── database.py              # Engine, session factory, Base
│   ├── models/
│   │   ├── __init__.py          # Re-exports all models for Alembic
│   │   ├── product.py           # Product, ProductVariant, ProductImage
│   │   ├── collection.py        # Collection, CollectionProduct
│   │   ├── inventory.py         # InventoryItem, InventoryLevel, Location
│   │   ├── customer.py          # Customer, CustomerAddress
│   │   ├── order.py             # Order, LineItem, Fulfillment
│   │   └── discount.py          # Discount
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── product.py           # Pydantic models for products/variants/images
│   │   ├── collection.py        # Pydantic models for collections
│   │   ├── inventory.py         # Pydantic models for inventory ops
│   │   ├── customer.py          # Pydantic models for customers
│   │   ├── order.py             # Pydantic models for orders/line items
│   │   ├── fulfillment.py       # Pydantic models for fulfillments
│   │   └── discount.py          # Pydantic models for discounts
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py              # Dependency injection (get_db)
│   │   ├── products.py          # Product + variant routes
│   │   ├── collections.py       # Collection routes
│   │   ├── inventory.py         # Inventory set/adjust routes
│   │   ├── customers.py         # Customer routes
│   │   ├── orders.py            # Order routes
│   │   ├── fulfillments.py      # Fulfillment routes
│   │   └── discounts.py         # Discount lookup route
│   ├── services/
│   │   ├── __init__.py
│   │   ├── inventory.py         # Atomic inventory operations
│   │   └── order.py             # Order creation with inventory deduction
│   └── ws/
│       ├── __init__.py
│       └── manager.py           # WebSocket connection manager + broadcast
├── tests/
│   ├── conftest.py              # Fixtures: test DB, client, seed data
│   ├── test_products.py
│   ├── test_collections.py
│   ├── test_inventory.py
│   ├── test_customers.py
│   ├── test_orders.py
│   ├── test_fulfillments.py
│   └── test_discounts.py
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── seed.py                      # Seed script for dev data
```

### Frontend

```
frontend/
├── package.json                 # pnpm workspace root
├── pnpm-workspace.yaml
├── packages/
│   ├── shared/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── api.ts           # Typed fetch wrapper
│   │       ├── types.ts         # Shared TypeScript types matching API
│   │       ├── useWebSocket.ts  # WebSocket hook for inventory updates
│   │       ├── ProductCard.tsx  # Reusable product card component
│   │       ├── DataTable.tsx    # Reusable table with sorting/filtering
│   │       └── SearchInput.tsx  # Debounced search input
│   ├── store/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx          # Router setup
│   │       ├── pages/
│   │       │   ├── ShopPage.tsx
│   │       │   ├── CartCheckoutPage.tsx
│   │       │   └── OrderStatusPage.tsx
│   │       ├── components/
│   │       │   ├── CartSidebar.tsx
│   │       │   └── CheckoutForm.tsx
│   │       └── store/
│   │           └── cartStore.ts # Simple cart state (React context or zustand)
│   ├── admin/
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── index.html
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       └── pages/
│   │           ├── ProductsInventoryPage.tsx
│   │           └── OrdersPage.tsx
│   └── pos/
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── index.html
│       └── src/
│           ├── main.tsx
│           ├── App.tsx
│           └── pages/
│               └── SalePage.tsx
```

### Root

```
docker-compose.yml
nginx.conf
.env.example
.gitignore
```

---

## Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/ws/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.12
uvicorn[standard]==0.34.2
sqlalchemy[asyncio]==2.0.40
asyncpg==0.30.0
alembic==1.15.2
pydantic==2.11.1
pydantic-settings==2.8.1
python-multipart==0.0.20
httpx==0.28.1
pytest==8.3.5
pytest-asyncio==0.26.0
```

- [ ] **Step 2: Create config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket"
    upload_dir: str = "uploads"

    model_config = {"env_prefix": ""}


settings = Settings()
```

- [ ] **Step 3: Create database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 4: Create api/deps.py**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session
```

- [ ] **Step 5: Create main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="OpenMarket API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create empty __init__.py files**

Create empty `__init__.py` in: `app/`, `app/api/`, `app/models/`, `app/schemas/`, `app/services/`, `app/ws/`, `tests/`.

- [ ] **Step 7: Create test config and verify app starts**

Create `backend/tests/conftest.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
```

Create `backend/tests/test_health.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 8: Run test to verify scaffolding works**

Run: `cd backend && pip install -r requirements.txt && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git init
git add backend/
git commit -m "feat: scaffold backend with FastAPI, config, database setup"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/app/models/product.py`
- Create: `backend/app/models/collection.py`
- Create: `backend/app/models/inventory.py`
- Create: `backend/app/models/customer.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/discount.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create product models**

Create `backend/app/models/product.py`:

```python
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    handle = Column(String, unique=True, nullable=False)
    description = Column(Text, default="")
    product_type = Column(String, default="")
    status = Column(String, default="active")  # active / draft / archived
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="Default")
    sku = Column(String, default="")
    barcode = Column(String, default="")
    price = Column(Numeric(10, 2), nullable=False)
    compare_at_price = Column(Numeric(10, 2), nullable=True)
    position = Column(Integer, default=0)

    product = relationship("Product", back_populates="variants")
    inventory_item = relationship("InventoryItem", back_populates="variant", uselist=False, cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    src = Column(String, nullable=False)
    position = Column(Integer, default=0)

    product = relationship("Product", back_populates="images")
```

- [ ] **Step 2: Create collection models**

Create `backend/app/models/collection.py`:

```python
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    handle = Column(String, unique=True, nullable=False)
    collection_type = Column(String, default="manual")  # manual / automated
    rules = Column(JSON, nullable=True)

    products = relationship("CollectionProduct", back_populates="collection", cascade="all, delete-orphan")


class CollectionProduct(Base):
    __tablename__ = "collection_products"

    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    position = Column(Integer, default=0)

    collection = relationship("Collection", back_populates="products")
    product = relationship("Product")
```

- [ ] **Step 3: Create inventory models**

Create `backend/app/models/inventory.py`:

```python
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, default="")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), unique=True, nullable=False)
    cost = Column(Numeric(10, 2), nullable=True)

    variant = relationship("ProductVariant", back_populates="inventory_item")
    levels = relationship("InventoryLevel", back_populates="inventory_item", cascade="all, delete-orphan")


class InventoryLevel(Base):
    __tablename__ = "inventory_levels"

    id = Column(Integer, primary_key=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    available = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=5)

    inventory_item = relationship("InventoryItem", back_populates="levels")
    location = relationship("Location")
```

- [ ] **Step 4: Create customer models**

Create `backend/app/models/customer.py`:

```python
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone = Column(String, default="")

    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    address1 = Column(String, nullable=False)
    city = Column(String, nullable=False)
    zip = Column(String, nullable=False)
    is_default = Column(Boolean, default=False)

    customer = relationship("Customer", back_populates="addresses")
```

- [ ] **Step 5: Create order models**

Create `backend/app/models/order.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    order_number = Column(String, unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    source = Column(String, nullable=False)  # web / pos
    fulfillment_status = Column(String, default="unfulfilled")  # unfulfilled / fulfilled
    total_price = Column(Numeric(10, 2), nullable=False)
    shipping_address = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer")
    line_items = relationship("LineItem", back_populates="order", cascade="all, delete-orphan")
    fulfillments = relationship("Fulfillment", back_populates="order", cascade="all, delete-orphan")


class LineItem(Base):
    __tablename__ = "line_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=False)
    title = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="line_items")
    variant = relationship("ProductVariant")


class Fulfillment(Base):
    __tablename__ = "fulfillments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="pending")  # pending / in_transit / delivered
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="fulfillments")
```

- [ ] **Step 6: Create discount model**

Create `backend/app/models/discount.py`:

```python
from sqlalchemy import Column, DateTime, Integer, Numeric, String

from app.database import Base


class Discount(Base):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    discount_type = Column(String, nullable=False)  # percentage / fixed_amount
    value = Column(Numeric(10, 2), nullable=False)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 7: Update models/__init__.py to re-export all models**

```python
from app.models.product import Product, ProductVariant, ProductImage
from app.models.collection import Collection, CollectionProduct
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.customer import Customer, CustomerAddress
from app.models.order import Order, LineItem, Fulfillment
from app.models.discount import Discount

__all__ = [
    "Product", "ProductVariant", "ProductImage",
    "Collection", "CollectionProduct",
    "Location", "InventoryItem", "InventoryLevel",
    "Customer", "CustomerAddress",
    "Order", "LineItem", "Fulfillment",
    "Discount",
]
```

- [ ] **Step 8: Write test to verify all models import and have correct table names**

Create `backend/tests/test_models.py`:

```python
import pytest
from app.models import (
    Product, ProductVariant, ProductImage,
    Collection, CollectionProduct,
    Location, InventoryItem, InventoryLevel,
    Customer, CustomerAddress,
    Order, LineItem, Fulfillment,
    Discount,
)


def test_product_table_name():
    assert Product.__tablename__ == "products"


def test_product_variant_table_name():
    assert ProductVariant.__tablename__ == "product_variants"


def test_product_image_table_name():
    assert ProductImage.__tablename__ == "product_images"


def test_collection_table_name():
    assert Collection.__tablename__ == "collections"


def test_collection_product_table_name():
    assert CollectionProduct.__tablename__ == "collection_products"


def test_location_table_name():
    assert Location.__tablename__ == "locations"


def test_inventory_item_table_name():
    assert InventoryItem.__tablename__ == "inventory_items"


def test_inventory_level_table_name():
    assert InventoryLevel.__tablename__ == "inventory_levels"


def test_customer_table_name():
    assert Customer.__tablename__ == "customers"


def test_customer_address_table_name():
    assert CustomerAddress.__tablename__ == "customer_addresses"


def test_order_table_name():
    assert Order.__tablename__ == "orders"


def test_line_item_table_name():
    assert LineItem.__tablename__ == "line_items"


def test_fulfillment_table_name():
    assert Fulfillment.__tablename__ == "fulfillments"


def test_discount_table_name():
    assert Discount.__tablename__ == "discounts"
```

- [ ] **Step 9: Run tests**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: All 14 PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add all SQLAlchemy models"
```

---

## Task 3: Alembic Setup & Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`

- [ ] **Step 1: Initialize Alembic**

Run: `cd backend && python -m alembic init alembic`

- [ ] **Step 2: Update alembic.ini**

In `backend/alembic.ini`, replace the `sqlalchemy.url` line:

```ini
sqlalchemy.url = postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket
```

- [ ] **Step 3: Update alembic/env.py for async and model discovery**

Replace `backend/alembic/env.py` with:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
from app.models import *  # noqa: F401, F403 — registers all models with Base
from app.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = settings.database_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Generate initial migration**

Run: `cd backend && python -m alembic revision --autogenerate -m "initial schema"`
Expected: Creates a migration file in `alembic/versions/`

- [ ] **Step 5: Apply migration (requires running PostgreSQL)**

Run: `cd backend && python -m alembic upgrade head`
Expected: All tables created

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: add Alembic setup with initial migration"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/product.py`
- Create: `backend/app/schemas/collection.py`
- Create: `backend/app/schemas/inventory.py`
- Create: `backend/app/schemas/customer.py`
- Create: `backend/app/schemas/order.py`
- Create: `backend/app/schemas/fulfillment.py`
- Create: `backend/app/schemas/discount.py`

- [ ] **Step 1: Create product schemas**

Create `backend/app/schemas/product.py`:

```python
from decimal import Decimal

from pydantic import BaseModel


class ProductImageOut(BaseModel):
    id: int
    src: str
    position: int

    model_config = {"from_attributes": True}


class VariantCreate(BaseModel):
    title: str = "Default"
    sku: str = ""
    barcode: str = ""
    price: Decimal
    compare_at_price: Decimal | None = None
    position: int = 0


class VariantUpdate(BaseModel):
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = None
    compare_at_price: Decimal | None = None
    position: int | None = None


class VariantOut(BaseModel):
    id: int
    product_id: int
    title: str
    sku: str
    barcode: str
    price: Decimal
    compare_at_price: Decimal | None
    position: int

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    title: str
    handle: str
    description: str = ""
    product_type: str = ""
    status: str = "active"
    tags: list[str] = []
    variants: list[VariantCreate] = []


class ProductUpdate(BaseModel):
    title: str | None = None
    handle: str | None = None
    description: str | None = None
    product_type: str | None = None
    status: str | None = None
    tags: list[str] | None = None


class ProductOut(BaseModel):
    id: int
    title: str
    handle: str
    description: str
    product_type: str
    status: str
    tags: list[str]
    variants: list[VariantOut] = []
    images: list[ProductImageOut] = []

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    id: int
    title: str
    handle: str
    product_type: str
    status: str
    tags: list[str]

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Create collection schemas**

Create `backend/app/schemas/collection.py`:

```python
from pydantic import BaseModel


class CollectionCreate(BaseModel):
    title: str
    handle: str
    collection_type: str = "manual"
    rules: dict | None = None


class CollectionUpdate(BaseModel):
    title: str | None = None
    handle: str | None = None
    rules: dict | None = None


class CollectionOut(BaseModel):
    id: int
    title: str
    handle: str
    collection_type: str
    rules: dict | None

    model_config = {"from_attributes": True}


class CollectionProductAdd(BaseModel):
    product_id: int
    position: int = 0
```

- [ ] **Step 3: Create inventory schemas**

Create `backend/app/schemas/inventory.py`:

```python
from decimal import Decimal

from pydantic import BaseModel


class InventoryLevelOut(BaseModel):
    id: int
    inventory_item_id: int
    location_id: int
    available: int
    low_stock_threshold: int
    variant_id: int | None = None

    model_config = {"from_attributes": True}


class InventorySet(BaseModel):
    inventory_item_id: int
    location_id: int
    available: int


class InventoryAdjust(BaseModel):
    inventory_item_id: int
    location_id: int
    available_adjustment: int  # positive or negative delta
```

- [ ] **Step 4: Create customer schemas**

Create `backend/app/schemas/customer.py`:

```python
from pydantic import BaseModel


class AddressCreate(BaseModel):
    address1: str
    city: str
    zip: str
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    address1: str
    city: str
    zip: str
    is_default: bool

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    email: str | None = None
    first_name: str
    last_name: str
    phone: str = ""
    addresses: list[AddressCreate] = []


class CustomerOut(BaseModel):
    id: int
    email: str | None
    first_name: str
    last_name: str
    phone: str
    addresses: list[AddressOut] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create order schemas**

Create `backend/app/schemas/order.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LineItemCreate(BaseModel):
    variant_id: int
    quantity: int


class LineItemOut(BaseModel):
    id: int
    variant_id: int
    title: str
    quantity: int
    price: Decimal

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    source: str  # web / pos
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    shipping_address: dict | None = None
    line_items: list[LineItemCreate]


class OrderUpdate(BaseModel):
    fulfillment_status: str | None = None


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int | None
    source: str
    fulfillment_status: str
    total_price: Decimal
    shipping_address: dict | None
    created_at: datetime
    line_items: list[LineItemOut] = []

    model_config = {"from_attributes": True}


class OrderListOut(BaseModel):
    id: int
    order_number: str
    source: str
    fulfillment_status: str
    total_price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 6: Create fulfillment schemas**

Create `backend/app/schemas/fulfillment.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class FulfillmentCreate(BaseModel):
    status: str = "pending"


class FulfillmentUpdate(BaseModel):
    status: str  # pending / in_transit / delivered


class FulfillmentOut(BaseModel):
    id: int
    order_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 7: Create discount schemas**

Create `backend/app/schemas/discount.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DiscountOut(BaseModel):
    id: int
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add all Pydantic schemas"
```

---

## Task 5: Test Infrastructure (DB fixtures)

**Files:**
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Set up async test database fixtures**

Replace `backend/tests/conftest.py` with:

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.main import app
from app.api.deps import get_db
from app.models import *  # noqa: F401, F403

TEST_DB_URL = "postgresql+asyncpg://openmarket:openmarket@localhost:5432/openmarket_test"

engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Ensure openmarket_test database exists**

Run: `createdb openmarket_test` (or `psql -c "CREATE DATABASE openmarket_test;"`)

- [ ] **Step 3: Run existing tests against new fixtures**

Run: `cd backend && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "feat: add async test DB fixtures"
```

---

## Task 6: Product & Variant API

**Files:**
- Create: `backend/app/api/products.py`
- Create: `backend/tests/test_products.py`
- Modify: `backend/app/main.py` (add router)

- [ ] **Step 1: Write failing tests for product CRUD**

Create `backend/tests/test_products.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_product(client):
    response = await client.post("/api/products", json={
        "title": "Whole Milk",
        "handle": "whole-milk",
        "product_type": "dairy",
        "variants": [
            {"title": "1L", "barcode": "1234567890", "price": "2.99"},
            {"title": "2L", "barcode": "1234567891", "price": "4.99"},
        ],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Whole Milk"
    assert data["handle"] == "whole-milk"
    assert len(data["variants"]) == 2
    assert data["variants"][0]["barcode"] == "1234567890"


@pytest.mark.asyncio
async def test_list_products(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    await client.post("/api/products", json={
        "title": "Bread", "handle": "bread", "variants": [{"price": "1.99"}],
    })
    response = await client.get("/api/products")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.get(f"/api/products/{pid}")
    assert response.status_code == 200
    assert response.json()["title"] == "Milk"


@pytest.mark.asyncio
async def test_update_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.put(f"/api/products/{pid}", json={"title": "Organic Milk"})
    assert response.status_code == 200
    assert response.json()["title"] == "Organic Milk"


@pytest.mark.asyncio
async def test_archive_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.delete(f"/api/products/{pid}")
    assert response.status_code == 200
    get = await client.get(f"/api/products/{pid}")
    assert get.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_add_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.post(f"/api/products/{pid}/variants", json={
        "title": "500ml", "barcode": "999", "price": "1.49",
    })
    assert response.status_code == 201
    assert response.json()["title"] == "500ml"


@pytest.mark.asyncio
async def test_update_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    vid = create.json()["variants"][0]["id"]
    response = await client.put(f"/api/variants/{vid}", json={"price": "3.49"})
    assert response.status_code == 200
    assert response.json()["price"] == "3.49"


@pytest.mark.asyncio
async def test_delete_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk",
        "handle": "milk",
        "variants": [
            {"title": "1L", "price": "2.99"},
            {"title": "2L", "price": "4.99"},
        ],
    })
    vid = create.json()["variants"][0]["id"]
    response = await client.delete(f"/api/variants/{vid}")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_products.py -v`
Expected: FAIL (404 — routes don't exist yet)

- [ ] **Step 3: Implement product API**

Create `backend/app/api/products.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.product import Product, ProductVariant
from app.models.inventory import InventoryItem
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductListOut,
    VariantCreate, VariantUpdate, VariantOut,
)

router = APIRouter(prefix="/api", tags=["products"])


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = Product(
        title=body.title,
        handle=body.handle,
        description=body.description,
        product_type=body.product_type,
        status=body.status,
        tags=body.tags,
    )
    for v in body.variants:
        variant = ProductVariant(**v.model_dump())
        variant.inventory_item = InventoryItem()
        product.variants.append(variant)
    db.add(product)
    await db.commit()
    await db.refresh(product, ["variants", "images"])
    return product


@router.get("/products", response_model=list[ProductListOut])
async def list_products(
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    result = await db.execute(query.order_by(Product.id))
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: int, body: ProductUpdate, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/products/{product_id}", response_model=ProductOut)
async def archive_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = "archived"
    await db.commit()
    await db.refresh(product)
    return product


@router.post("/products/{product_id}/variants", response_model=VariantOut, status_code=201)
async def add_variant(product_id: int, body: VariantCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = ProductVariant(product_id=product_id, **body.model_dump())
    variant.inventory_item = InventoryItem()
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.put("/variants/{variant_id}", response_model=VariantOut)
async def update_variant(variant_id: int, body: VariantUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(variant, key, value)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.delete("/variants/{variant_id}")
async def delete_variant(variant_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    await db.delete(variant)
    await db.commit()
    return {"ok": True}
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py` after the CORS middleware:

```python
from app.api.products import router as products_router

app.include_router(products_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_products.py -v`
Expected: All 8 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/products.py backend/app/main.py backend/tests/test_products.py
git commit -m "feat: add product and variant CRUD API"
```

---

## Task 7: Collection API

**Files:**
- Create: `backend/app/api/collections.py`
- Create: `backend/tests/test_collections.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_collections.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_collection(client):
    response = await client.post("/api/collections", json={
        "title": "Dairy", "handle": "dairy",
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Dairy"


@pytest.mark.asyncio
async def test_list_collections(client):
    await client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    await client.post("/api/collections", json={"title": "Bakery", "handle": "bakery"})
    response = await client.get("/api/collections")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_collection_products(client):
    col = await client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    cid = col.json()["id"]
    prod = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = prod.json()["id"]
    await client.post(f"/api/collections/{cid}/products", json={"product_id": pid})
    response = await client.get(f"/api/collections/{cid}/products")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Milk"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_collections.py -v`
Expected: FAIL

- [ ] **Step 3: Implement collection API**

Create `backend/app/api/collections.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.collection import Collection, CollectionProduct
from app.models.product import Product
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionOut, CollectionProductAdd
from app.schemas.product import ProductListOut

router = APIRouter(prefix="/api", tags=["collections"])


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(body: CollectionCreate, db: AsyncSession = Depends(get_db)):
    collection = Collection(**body.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).order_by(Collection.id))
    return result.scalars().all()


@router.put("/collections/{collection_id}", response_model=CollectionOut)
async def update_collection(collection_id: int, body: CollectionUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(collection, key, value)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.post("/collections/{collection_id}/products", status_code=201)
async def add_product_to_collection(
    collection_id: int, body: CollectionProductAdd, db: AsyncSession = Depends(get_db),
):
    cp = CollectionProduct(collection_id=collection_id, product_id=body.product_id, position=body.position)
    db.add(cp)
    await db.commit()
    return {"ok": True}


@router.get("/collections/{collection_id}/products", response_model=list[ProductListOut])
async def get_collection_products(collection_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .join(CollectionProduct, CollectionProduct.product_id == Product.id)
        .where(CollectionProduct.collection_id == collection_id)
        .order_by(CollectionProduct.position)
    )
    result = await db.execute(query)
    return result.scalars().all()
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.collections import router as collections_router

app.include_router(collections_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_collections.py -v`
Expected: All 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/collections.py backend/app/main.py backend/tests/test_collections.py
git commit -m "feat: add collection API"
```

---

## Task 8: WebSocket Manager

**Files:**
- Create: `backend/app/ws/manager.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create WebSocket manager**

Create `backend/app/ws/manager.py`:

```python
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)


manager = ConnectionManager()
```

- [ ] **Step 2: Add WebSocket endpoint to main.py**

Add to `backend/app/main.py`:

```python
from fastapi import WebSocket, WebSocketDisconnect
from app.ws.manager import manager


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

- [ ] **Step 3: Write test for WebSocket**

Create `backend/tests/test_websocket.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ws.manager import manager


@pytest.mark.asyncio
async def test_websocket_connect():
    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        with tc.websocket_connect("/api/ws") as ws:
            assert len(manager.active_connections) == 1
        assert len(manager.active_connections) == 0
```

- [ ] **Step 4: Run test**

Run: `cd backend && python -m pytest tests/test_websocket.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/ws/ backend/app/main.py backend/tests/test_websocket.py
git commit -m "feat: add WebSocket connection manager"
```

---

## Task 9: Inventory API with Atomic Updates & WebSocket Broadcast

**Files:**
- Create: `backend/app/services/inventory.py`
- Create: `backend/app/api/inventory.py`
- Create: `backend/tests/test_inventory.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_inventory.py`:

```python
import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_product_with_inventory(db):
    """Create a product with a variant, inventory item, location, and inventory level."""
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()

    product = Product(title="Milk", handle="milk", status="active", tags=[])
    db.add(product)
    await db.flush()

    variant = ProductVariant(product_id=product.id, title="1L", price=2.99, barcode="123")
    db.add(variant)
    await db.flush()

    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()

    level = InventoryLevel(
        inventory_item_id=inv_item.id, location_id=location.id, available=50,
    )
    db.add(level)
    await db.commit()

    return {"location_id": location.id, "inventory_item_id": inv_item.id, "variant_id": variant.id}


@pytest.mark.asyncio
async def test_get_inventory_levels(client, db):
    ids = await seed_product_with_inventory(db)
    response = await client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["available"] == 50


@pytest.mark.asyncio
async def test_set_inventory(client, db):
    ids = await seed_product_with_inventory(db)
    response = await client.post("/api/inventory-levels/set", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available": 100,
    })
    assert response.status_code == 200
    assert response.json()["available"] == 100


@pytest.mark.asyncio
async def test_adjust_inventory(client, db):
    ids = await seed_product_with_inventory(db)
    response = await client.post("/api/inventory-levels/adjust", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available_adjustment": -5,
    })
    assert response.status_code == 200
    assert response.json()["available"] == 45


@pytest.mark.asyncio
async def test_adjust_inventory_prevents_oversell(client, db):
    ids = await seed_product_with_inventory(db)
    response = await client.post("/api/inventory-levels/adjust", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available_adjustment": -999,
    })
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_inventory.py -v`
Expected: FAIL

- [ ] **Step 3: Implement inventory service**

Create `backend/app/services/inventory.py`:

```python
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryLevel
from app.ws.manager import manager


async def set_inventory(db: AsyncSession, inventory_item_id: int, location_id: int, available: int) -> InventoryLevel:
    result = await db.execute(
        select(InventoryLevel).where(
            InventoryLevel.inventory_item_id == inventory_item_id,
            InventoryLevel.location_id == location_id,
        )
    )
    level = result.scalar_one()
    level.available = available
    await db.commit()
    await db.refresh(level)
    await _broadcast(level)
    return level


async def adjust_inventory(db: AsyncSession, inventory_item_id: int, location_id: int, delta: int) -> InventoryLevel | None:
    # Atomic update that prevents going below zero
    result = await db.execute(
        text("""
            UPDATE inventory_levels
            SET available = available + :delta
            WHERE inventory_item_id = :inv_id AND location_id = :loc_id
              AND available + :delta >= 0
            RETURNING id
        """),
        {"delta": delta, "inv_id": inventory_item_id, "loc_id": location_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    await db.commit()

    level_result = await db.execute(
        select(InventoryLevel).where(InventoryLevel.id == row.id)
    )
    level = level_result.scalar_one()
    await _broadcast(level)
    return level


async def _broadcast(level: InventoryLevel):
    await manager.broadcast({
        "type": "inventory_updated",
        "inventory_item_id": level.inventory_item_id,
        "location_id": level.location_id,
        "available": level.available,
    })
```

- [ ] **Step 4: Implement inventory API**

Create `backend/app/api/inventory.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.inventory import InventoryLevel
from app.schemas.inventory import InventoryLevelOut, InventorySet, InventoryAdjust
from app.services.inventory import set_inventory, adjust_inventory

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory-levels", response_model=list[InventoryLevelOut])
async def get_inventory_levels(location_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InventoryLevel).where(InventoryLevel.location_id == location_id)
    )
    return result.scalars().all()


@router.post("/inventory-levels/set", response_model=InventoryLevelOut)
async def set_level(body: InventorySet, db: AsyncSession = Depends(get_db)):
    level = await set_inventory(db, body.inventory_item_id, body.location_id, body.available)
    return level


@router.post("/inventory-levels/adjust", response_model=InventoryLevelOut)
async def adjust_level(body: InventoryAdjust, db: AsyncSession = Depends(get_db)):
    level = await adjust_inventory(db, body.inventory_item_id, body.location_id, body.available_adjustment)
    if level is None:
        raise HTTPException(status_code=409, detail="Insufficient stock")
    return level
```

- [ ] **Step 5: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.inventory import router as inventory_router

app.include_router(inventory_router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_inventory.py -v`
Expected: All 4 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/inventory.py backend/app/api/inventory.py backend/app/main.py backend/tests/test_inventory.py
git commit -m "feat: add inventory API with atomic updates and WebSocket broadcast"
```

---

## Task 10: Customer API

**Files:**
- Create: `backend/app/api/customers.py`
- Create: `backend/tests/test_customers.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_customers.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_create_customer(client):
    response = await client.post("/api/customers", json={
        "first_name": "John",
        "last_name": "Doe",
        "phone": "555-1234",
        "addresses": [{"address1": "123 Main St", "city": "Seoul", "zip": "12345", "is_default": True}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert len(data["addresses"]) == 1


@pytest.mark.asyncio
async def test_list_customers(client):
    await client.post("/api/customers", json={
        "first_name": "John", "last_name": "Doe",
    })
    response = await client.get("/api/customers")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_customer(client):
    create = await client.post("/api/customers", json={
        "first_name": "John", "last_name": "Doe",
    })
    cid = create.json()["id"]
    response = await client.get(f"/api/customers/{cid}")
    assert response.status_code == 200
    assert response.json()["first_name"] == "John"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_customers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement customer API**

Create `backend/app/api/customers.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.customer import Customer, CustomerAddress
from app.schemas.customer import CustomerCreate, CustomerOut

router = APIRouter(prefix="/api", tags=["customers"])


@router.post("/customers", response_model=CustomerOut, status_code=201)
async def create_customer(body: CustomerCreate, db: AsyncSession = Depends(get_db)):
    customer = Customer(
        email=body.email,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
    )
    for addr in body.addresses:
        customer.addresses.append(CustomerAddress(**addr.model_dump()))
    db.add(customer)
    await db.commit()
    await db.refresh(customer, ["addresses"])
    return customer


@router.get("/customers", response_model=list[CustomerOut])
async def list_customers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Customer).options(selectinload(Customer.addresses)).order_by(Customer.id)
    )
    return result.scalars().all()


@router.get("/customers/{customer_id}", response_model=CustomerOut)
async def get_customer(customer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Customer)
        .where(Customer.id == customer_id)
        .options(selectinload(Customer.addresses))
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
```

- [ ] **Step 4: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.customers import router as customers_router

app.include_router(customers_router)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_customers.py -v`
Expected: All 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/customers.py backend/app/main.py backend/tests/test_customers.py
git commit -m "feat: add customer API"
```

---

## Task 11: Order API with Inventory Deduction

**Files:**
- Create: `backend/app/services/order.py`
- Create: `backend/app/api/orders.py`
- Create: `backend/tests/test_orders.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_orders.py`:

```python
import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_for_order(db):
    """Create product, variant, inventory ready for ordering."""
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()

    product = Product(title="Milk", handle="milk", status="active", tags=[])
    db.add(product)
    await db.flush()

    variant = ProductVariant(product_id=product.id, title="1L", price=2.99, barcode="123")
    db.add(variant)
    await db.flush()

    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()

    level = InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=50)
    db.add(level)
    await db.commit()

    return {"variant_id": variant.id, "location_id": location.id, "inv_item_id": inv_item.id}


@pytest.mark.asyncio
async def test_create_web_order(client, db):
    ids = await seed_for_order(db)
    response = await client.post("/api/orders", json={
        "source": "web",
        "customer_name": "John Doe",
        "customer_phone": "555-1234",
        "shipping_address": {"address1": "123 Main St", "city": "Seoul", "zip": "12345"},
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 2}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "web"
    assert data["fulfillment_status"] == "unfulfilled"
    assert data["total_price"] == "5.98"
    assert len(data["line_items"]) == 1


@pytest.mark.asyncio
async def test_create_pos_order(client, db):
    ids = await seed_for_order(db)
    response = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 3}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "pos"
    assert data["fulfillment_status"] == "fulfilled"


@pytest.mark.asyncio
async def test_order_deducts_inventory(client, db):
    ids = await seed_for_order(db)
    await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 5}],
    })
    inv = await client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert inv.json()[0]["available"] == 45


@pytest.mark.asyncio
async def test_order_fails_on_insufficient_stock(client, db):
    ids = await seed_for_order(db)
    response = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 999}],
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_orders(client, db):
    ids = await seed_for_order(db)
    await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    response = await client.get("/api/orders")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_order(client, db):
    ids = await seed_for_order(db)
    create = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    oid = create.json()["id"]
    response = await client.get(f"/api/orders/{oid}")
    assert response.status_code == 200
    assert len(response.json()["line_items"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_orders.py -v`
Expected: FAIL

- [ ] **Step 3: Implement order service**

Create `backend/app/services/order.py`:

```python
import itertools

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem, InventoryLevel
from app.models.order import Order, LineItem
from app.models.product import ProductVariant
from app.ws.manager import manager

_order_counter = itertools.count(1001)


async def create_order(
    db: AsyncSession,
    source: str,
    line_items_data: list[dict],
    customer_id: int | None = None,
    shipping_address: dict | None = None,
) -> Order:
    # Resolve variants and compute total
    total = 0
    line_items = []
    inventory_adjustments = []

    for item_data in line_items_data:
        variant_result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == item_data["variant_id"])
        )
        variant = variant_result.scalar_one()

        line_total = variant.price * item_data["quantity"]
        total += line_total

        line_items.append(LineItem(
            variant_id=variant.id,
            title=f"{variant.product_id}:{variant.title}",
            quantity=item_data["quantity"],
            price=variant.price,
        ))

        # Find inventory item for this variant
        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.variant_id == variant.id)
        )
        inv_item = inv_result.scalar_one()
        inventory_adjustments.append((inv_item.id, -item_data["quantity"]))

    # Atomic inventory deduction for all line items
    for inv_item_id, delta in inventory_adjustments:
        result = await db.execute(
            text("""
                UPDATE inventory_levels
                SET available = available + :delta
                WHERE inventory_item_id = :inv_id AND available + :delta >= 0
                RETURNING id, available, location_id
            """),
            {"delta": delta, "inv_id": inv_item_id},
        )
        row = result.fetchone()
        if row is None:
            await db.rollback()
            raise ValueError("Insufficient stock")

        await manager.broadcast({
            "type": "inventory_updated",
            "inventory_item_id": inv_item_id,
            "location_id": row.location_id,
            "available": row.available,
        })

    # Generate order number
    # In production, use a DB sequence. For now, use timestamp-based.
    from datetime import datetime
    order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{next(_order_counter)}"

    order = Order(
        order_number=order_number,
        customer_id=customer_id,
        source=source,
        fulfillment_status="fulfilled" if source == "pos" else "unfulfilled",
        total_price=total,
        shipping_address=shipping_address,
    )
    for li in line_items:
        order.line_items.append(li)

    db.add(order)
    await db.commit()
    await db.refresh(order, ["line_items"])
    return order
```

- [ ] **Step 4: Implement orders API**

Create `backend/app/api/orders.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate, OrderOut, OrderListOut
from app.services.order import create_order

router = APIRouter(prefix="/api", tags=["orders"])


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create(body: OrderCreate, db: AsyncSession = Depends(get_db)):
    try:
        order = await create_order(
            db=db,
            source=body.source,
            line_items_data=[li.model_dump() for li in body.line_items],
            customer_id=body.customer_id,
            shipping_address=body.shipping_address,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.get("/orders", response_model=list[OrderListOut])
async def list_orders(
    source: str | None = None,
    fulfillment_status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Order)
    if source:
        query = query.where(Order.source == source)
    if fulfillment_status:
        query = query.where(Order.fulfillment_status == fulfillment_status)
    result = await db.execute(query.order_by(Order.created_at.desc()))
    return result.scalars().all()


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.line_items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/orders/{order_id}", response_model=OrderOut)
async def update_order(order_id: int, body: OrderUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.line_items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    await db.commit()
    await db.refresh(order)
    return order
```

- [ ] **Step 5: Register router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.orders import router as orders_router

app.include_router(orders_router)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_orders.py -v`
Expected: All 6 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/order.py backend/app/api/orders.py backend/app/main.py backend/tests/test_orders.py
git commit -m "feat: add order API with atomic inventory deduction"
```

---

## Task 12: Fulfillment & Discount APIs

**Files:**
- Create: `backend/app/api/fulfillments.py`
- Create: `backend/app/api/discounts.py`
- Create: `backend/tests/test_fulfillments.py`
- Create: `backend/tests/test_discounts.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing fulfillment tests**

Create `backend/tests/test_fulfillments.py`:

```python
import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_and_create_order(client, db):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Milk", handle="milk", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="1L", price=2.99, barcode="123")
    db.add(variant)
    await db.flush()
    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()
    InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=50)
    db.add(InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=50))
    await db.commit()

    order = await client.post("/api/orders", json={
        "source": "web",
        "shipping_address": {"address1": "123 Main St", "city": "Seoul", "zip": "12345"},
        "line_items": [{"variant_id": variant.id, "quantity": 1}],
    })
    return order.json()["id"]


@pytest.mark.asyncio
async def test_create_fulfillment(client, db):
    order_id = await seed_and_create_order(client, db)
    response = await client.post(f"/api/orders/{order_id}/fulfillments", json={
        "status": "pending",
    })
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_update_fulfillment(client, db):
    order_id = await seed_and_create_order(client, db)
    create = await client.post(f"/api/orders/{order_id}/fulfillments", json={"status": "pending"})
    fid = create.json()["id"]
    response = await client.put(f"/api/fulfillments/{fid}", json={"status": "delivered"})
    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
```

- [ ] **Step 2: Write failing discount tests**

Create `backend/tests/test_discounts.py`:

```python
import pytest
from app.models.discount import Discount
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_lookup_valid_discount(client, db):
    discount = Discount(
        code="SAVE10",
        discount_type="percentage",
        value=10,
        starts_at=datetime.now(timezone.utc) - timedelta(days=1),
        ends_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(discount)
    await db.commit()

    response = await client.post("/api/discounts/lookup?code=SAVE10")
    assert response.status_code == 200
    assert response.json()["code"] == "SAVE10"
    assert response.json()["value"] == "10.00"


@pytest.mark.asyncio
async def test_lookup_expired_discount(client, db):
    discount = Discount(
        code="OLD10",
        discount_type="percentage",
        value=10,
        starts_at=datetime.now(timezone.utc) - timedelta(days=60),
        ends_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(discount)
    await db.commit()

    response = await client.post("/api/discounts/lookup?code=OLD10")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lookup_nonexistent_discount(client):
    response = await client.post("/api/discounts/lookup?code=NOPE")
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_fulfillments.py tests/test_discounts.py -v`
Expected: FAIL

- [ ] **Step 4: Implement fulfillment API**

Create `backend/app/api/fulfillments.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.order import Fulfillment, Order
from app.schemas.fulfillment import FulfillmentCreate, FulfillmentUpdate, FulfillmentOut

router = APIRouter(prefix="/api", tags=["fulfillments"])


@router.post("/orders/{order_id}/fulfillments", response_model=FulfillmentOut, status_code=201)
async def create_fulfillment(order_id: int, body: FulfillmentCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    fulfillment = Fulfillment(order_id=order_id, status=body.status)
    db.add(fulfillment)
    await db.commit()
    await db.refresh(fulfillment)
    return fulfillment


@router.put("/fulfillments/{fulfillment_id}", response_model=FulfillmentOut)
async def update_fulfillment(fulfillment_id: int, body: FulfillmentUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Fulfillment).where(Fulfillment.id == fulfillment_id))
    fulfillment = result.scalar_one_or_none()
    if not fulfillment:
        raise HTTPException(status_code=404, detail="Fulfillment not found")
    fulfillment.status = body.status

    if body.status == "delivered":
        order_result = await db.execute(select(Order).where(Order.id == fulfillment.order_id))
        order = order_result.scalar_one()
        order.fulfillment_status = "fulfilled"

    await db.commit()
    await db.refresh(fulfillment)
    return fulfillment
```

- [ ] **Step 5: Implement discount API**

Create `backend/app/api/discounts.py`:

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.discount import Discount
from app.schemas.discount import DiscountOut

router = APIRouter(prefix="/api", tags=["discounts"])


@router.post("/discounts/lookup", response_model=DiscountOut)
async def lookup_discount(code: str, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Discount).where(
            Discount.code == code,
            Discount.starts_at <= now,
            Discount.ends_at >= now,
        )
    )
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found or expired")
    return discount
```

- [ ] **Step 6: Register routers in main.py**

Add to `backend/app/main.py`:

```python
from app.api.fulfillments import router as fulfillments_router
from app.api.discounts import router as discounts_router

app.include_router(fulfillments_router)
app.include_router(discounts_router)
```

- [ ] **Step 7: Run tests**

Run: `cd backend && python -m pytest tests/test_fulfillments.py tests/test_discounts.py -v`
Expected: All 5 PASS

- [ ] **Step 8: Run full backend test suite**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/fulfillments.py backend/app/api/discounts.py backend/app/main.py backend/tests/test_fulfillments.py backend/tests/test_discounts.py
git commit -m "feat: add fulfillment and discount APIs"
```

---

## Task 13: Frontend Monorepo Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/pnpm-workspace.yaml`
- Create: `frontend/packages/shared/package.json`
- Create: `frontend/packages/shared/tsconfig.json`
- Create: `frontend/packages/shared/src/types.ts`
- Create: `frontend/packages/shared/src/api.ts`
- Create: `frontend/packages/shared/src/useWebSocket.ts`
- Create: `frontend/packages/shared/src/index.ts`

- [ ] **Step 1: Create root package.json and workspace config**

Create `frontend/package.json`:

```json
{
  "name": "openmarket-frontend",
  "private": true,
  "scripts": {
    "dev:store": "pnpm --filter @openmarket/store dev",
    "dev:admin": "pnpm --filter @openmarket/admin dev",
    "dev:pos": "pnpm --filter @openmarket/pos dev",
    "build": "pnpm -r build"
  }
}
```

Create `frontend/pnpm-workspace.yaml`:

```yaml
packages:
  - "packages/*"
```

- [ ] **Step 2: Create shared package**

Create `frontend/packages/shared/package.json`:

```json
{
  "name": "@openmarket/shared",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "react": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "typescript": "^5.7.3"
  }
}
```

Create `frontend/packages/shared/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create shared types**

Create `frontend/packages/shared/src/types.ts`:

```typescript
export interface ProductVariant {
  id: number;
  product_id: number;
  title: string;
  sku: string;
  barcode: string;
  price: string;
  compare_at_price: string | null;
  position: number;
}

export interface ProductImage {
  id: number;
  src: string;
  position: number;
}

export interface Product {
  id: number;
  title: string;
  handle: string;
  description: string;
  product_type: string;
  status: string;
  tags: string[];
  variants: ProductVariant[];
  images: ProductImage[];
}

export interface ProductListItem {
  id: number;
  title: string;
  handle: string;
  product_type: string;
  status: string;
  tags: string[];
}

export interface Collection {
  id: number;
  title: string;
  handle: string;
  collection_type: string;
  rules: Record<string, unknown> | null;
}

export interface InventoryLevel {
  id: number;
  inventory_item_id: number;
  location_id: number;
  available: number;
  low_stock_threshold: number;
}

export interface Customer {
  id: number;
  email: string | null;
  first_name: string;
  last_name: string;
  phone: string;
  addresses: CustomerAddress[];
}

export interface CustomerAddress {
  id: number;
  address1: string;
  city: string;
  zip: string;
  is_default: boolean;
}

export interface LineItem {
  id: number;
  variant_id: number;
  title: string;
  quantity: number;
  price: string;
}

export interface Order {
  id: number;
  order_number: string;
  customer_id: number | null;
  source: string;
  fulfillment_status: string;
  total_price: string;
  shipping_address: Record<string, string> | null;
  created_at: string;
  line_items: LineItem[];
}

export interface OrderListItem {
  id: number;
  order_number: string;
  source: string;
  fulfillment_status: string;
  total_price: string;
  created_at: string;
}

export interface Fulfillment {
  id: number;
  order_id: number;
  status: string;
  created_at: string;
}

export interface Discount {
  id: number;
  code: string;
  discount_type: string;
  value: string;
  starts_at: string;
  ends_at: string;
}

export interface CartItem {
  variant: ProductVariant;
  product: Product;
  quantity: number;
}
```

- [ ] **Step 4: Create API client**

Create `frontend/packages/shared/src/api.ts`:

```typescript
const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export const api = {
  products: {
    list: (params?: { status?: string; search?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string>).toString();
      return request<import("./types").ProductListItem[]>(`/products${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Product>(`/products/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Product>("/products", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Record<string, unknown>) =>
      request<import("./types").Product>(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    archive: (id: number) =>
      request<import("./types").Product>(`/products/${id}`, { method: "DELETE" }),
  },

  collections: {
    list: () => request<import("./types").Collection[]>("/collections"),
    products: (id: number) =>
      request<import("./types").ProductListItem[]>(`/collections/${id}/products`),
  },

  inventory: {
    levels: (locationId: number) =>
      request<import("./types").InventoryLevel[]>(`/inventory-levels?location_id=${locationId}`),
    set: (data: { inventory_item_id: number; location_id: number; available: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/set", { method: "POST", body: JSON.stringify(data) }),
    adjust: (data: { inventory_item_id: number; location_id: number; available_adjustment: number }) =>
      request<import("./types").InventoryLevel>("/inventory-levels/adjust", { method: "POST", body: JSON.stringify(data) }),
  },

  orders: {
    list: (params?: { source?: string; fulfillment_status?: string }) => {
      const qs = new URLSearchParams(params as Record<string, string>).toString();
      return request<import("./types").OrderListItem[]>(`/orders${qs ? `?${qs}` : ""}`);
    },
    get: (id: number) => request<import("./types").Order>(`/orders/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Order>("/orders", { method: "POST", body: JSON.stringify(data) }),
  },

  fulfillments: {
    create: (orderId: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/orders/${orderId}/fulfillments`, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: { status: string }) =>
      request<import("./types").Fulfillment>(`/fulfillments/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  },

  discounts: {
    lookup: (code: string) =>
      request<import("./types").Discount>(`/discounts/lookup?code=${encodeURIComponent(code)}`, { method: "POST" }),
  },

  customers: {
    list: () => request<import("./types").Customer[]>("/customers"),
    get: (id: number) => request<import("./types").Customer>(`/customers/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("./types").Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
  },
};
```

- [ ] **Step 5: Create WebSocket hook**

Create `frontend/packages/shared/src/useWebSocket.ts`:

```typescript
import { useEffect, useRef, useCallback, useState } from "react";

interface InventoryUpdate {
  type: "inventory_updated";
  inventory_item_id: number;
  location_id: number;
  available: number;
}

export function useWebSocket(onInventoryUpdate: (update: InventoryUpdate) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as InventoryUpdate;
      if (data.type === "inventory_updated") {
        onInventoryUpdate(data);
      }
    };

    wsRef.current = ws;
  }, [onInventoryUpdate]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { connected };
}
```

- [ ] **Step 6: Create barrel export**

Create `frontend/packages/shared/src/index.ts`:

```typescript
export { api } from "./api";
export { useWebSocket } from "./useWebSocket";
export type * from "./types";
```

- [ ] **Step 7: Install dependencies**

Run: `cd frontend && pnpm install`

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/pnpm-workspace.yaml frontend/pnpm-lock.yaml frontend/packages/shared/
git commit -m "feat: scaffold frontend monorepo with shared package"
```

---

## Task 14: Store Frontend (Web Store)

**Files:**
- Create: `frontend/packages/store/package.json`
- Create: `frontend/packages/store/tsconfig.json`
- Create: `frontend/packages/store/vite.config.ts`
- Create: `frontend/packages/store/index.html`
- Create: `frontend/packages/store/src/main.tsx`
- Create: `frontend/packages/store/src/App.tsx`
- Create: `frontend/packages/store/src/store/cartStore.ts`
- Create: `frontend/packages/store/src/pages/ShopPage.tsx`
- Create: `frontend/packages/store/src/pages/CartCheckoutPage.tsx`
- Create: `frontend/packages/store/src/pages/OrderStatusPage.tsx`

- [ ] **Step 1: Create store package config**

Create `frontend/packages/store/package.json`:

```json
{
  "name": "@openmarket/store",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@openmarket/shared": "workspace:*",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.3",
    "vite": "^6.0.7"
  }
}
```

Create `frontend/packages/store/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist"
  },
  "include": ["src"],
  "references": [{ "path": "../shared" }]
}
```

Create `frontend/packages/store/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
```

Create `frontend/packages/store/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenMarket Store</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create main entry and App router**

Create `frontend/packages/store/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
```

Create `frontend/packages/store/src/App.tsx`:

```tsx
import { Routes, Route, Link } from "react-router-dom";
import { ShopPage } from "./pages/ShopPage";
import { CartCheckoutPage } from "./pages/CartCheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { CartProvider } from "./store/cartStore";

export function App() {
  return (
    <CartProvider>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #eee", display: "flex", gap: "1rem", alignItems: "center" }}>
        <Link to="/" style={{ fontWeight: "bold", fontSize: "1.2rem", textDecoration: "none" }}>
          OpenMarket
        </Link>
        <Link to="/cart">Cart</Link>
        <Link to="/order-status">Track Order</Link>
      </nav>
      <Routes>
        <Route path="/" element={<ShopPage />} />
        <Route path="/cart" element={<CartCheckoutPage />} />
        <Route path="/order-status" element={<OrderStatusPage />} />
      </Routes>
    </CartProvider>
  );
}
```

- [ ] **Step 3: Create cart store (React context)**

Create `frontend/packages/store/src/store/cartStore.tsx`:

```tsx
import { createContext, useContext, useState, ReactNode, useCallback } from "react";
import type { CartItem, Product, ProductVariant } from "@openmarket/shared";

interface CartContextType {
  items: CartItem[];
  addItem: (product: Product, variant: ProductVariant) => void;
  removeItem: (variantId: number) => void;
  updateQuantity: (variantId: number, quantity: number) => void;
  clearCart: () => void;
  total: number;
}

const CartContext = createContext<CartContextType | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const addItem = useCallback((product: Product, variant: ProductVariant) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) {
        return prev.map((i) =>
          i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i,
        );
      }
      return [...prev, { product, variant, quantity: 1 }];
    });
  }, []);

  const removeItem = useCallback((variantId: number) => {
    setItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  }, []);

  const updateQuantity = useCallback((variantId: number, quantity: number) => {
    if (quantity <= 0) {
      setItems((prev) => prev.filter((i) => i.variant.id !== variantId));
      return;
    }
    setItems((prev) =>
      prev.map((i) => (i.variant.id === variantId ? { ...i, quantity } : i)),
    );
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const total = items.reduce(
    (sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0,
  );

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQuantity, clearCart, total }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within CartProvider");
  return ctx;
}
```

- [ ] **Step 4: Create ShopPage**

Create `frontend/packages/store/src/pages/ShopPage.tsx`:

```tsx
import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductListItem } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function ShopPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [search, setSearch] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const { addItem } = useCart();

  useEffect(() => {
    api.products.list({ status: "active", search: search || undefined }).then(setProducts);
  }, [search]);

  const handleInventoryUpdate = useCallback(() => {
    // Refresh products on inventory change (could be more granular)
  }, []);

  useWebSocket(handleInventoryUpdate);

  const openProduct = async (id: number) => {
    const product = await api.products.get(id);
    setSelectedProduct(product);
  };

  return (
    <div style={{ display: "flex", padding: "1rem", gap: "1rem" }}>
      <div style={{ flex: 1 }}>
        <input
          type="text"
          placeholder="Search products..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: "100%", padding: "0.5rem", marginBottom: "1rem", boxSizing: "border-box" }}
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "1rem" }}>
          {products.map((p) => (
            <div
              key={p.id}
              onClick={() => openProduct(p.id)}
              style={{ border: "1px solid #ddd", padding: "1rem", cursor: "pointer", borderRadius: "4px" }}
            >
              <h3 style={{ margin: "0 0 0.5rem" }}>{p.title}</h3>
              <p style={{ margin: 0, color: "#666" }}>{p.product_type}</p>
            </div>
          ))}
        </div>
      </div>

      {selectedProduct && (
        <div style={{ width: 300, border: "1px solid #ddd", padding: "1rem", borderRadius: "4px" }}>
          <h2>{selectedProduct.title}</h2>
          <p>{selectedProduct.description}</p>
          <h4>Variants:</h4>
          {selectedProduct.variants.map((v) => (
            <div key={v.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <span>{v.title} - ${v.price}</span>
              <button onClick={() => addItem(selectedProduct, v)}>Add</button>
            </div>
          ))}
          <button onClick={() => setSelectedProduct(null)} style={{ marginTop: "1rem" }}>Close</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create CartCheckoutPage**

Create `frontend/packages/store/src/pages/CartCheckoutPage.tsx`:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@openmarket/shared";
import { useCart } from "../store/cartStore";

export function CartCheckoutPage() {
  const { items, updateQuantity, removeItem, clearCart, total } = useCart();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [zip, setZip] = useState("");
  const [discountCode, setDiscountCode] = useState("");
  const [discount, setDiscount] = useState<{ type: string; value: number } | null>(null);
  const [error, setError] = useState("");
  const [orderNumber, setOrderNumber] = useState("");

  const applyDiscount = async () => {
    try {
      const d = await api.discounts.lookup(discountCode);
      setDiscount({ type: d.discount_type, value: parseFloat(d.value) });
      setError("");
    } catch {
      setError("Invalid or expired discount code");
      setDiscount(null);
    }
  };

  const finalTotal = discount
    ? discount.type === "percentage"
      ? total * (1 - discount.value / 100)
      : Math.max(0, total - discount.value)
    : total;

  const placeOrder = async () => {
    try {
      const order = await api.orders.create({
        source: "web",
        customer_name: name,
        customer_phone: phone,
        shipping_address: { address1: address, city, zip },
        line_items: items.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
      });
      setOrderNumber(order.order_number);
      clearCart();
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (orderNumber) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <h2>Order Placed!</h2>
        <p>Your order number is: <strong>{orderNumber}</strong></p>
        <button onClick={() => navigate("/order-status")}>Track Order</button>
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem", maxWidth: 600, margin: "0 auto" }}>
      <h2>Cart</h2>
      {items.length === 0 ? (
        <p>Your cart is empty</p>
      ) : (
        <>
          {items.map((item) => (
            <div key={item.variant.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem 0", borderBottom: "1px solid #eee" }}>
              <div>
                <strong>{item.product.title}</strong> - {item.variant.title}
                <br />${item.variant.price} each
              </div>
              <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                <button onClick={() => updateQuantity(item.variant.id, item.quantity - 1)}>-</button>
                <span>{item.quantity}</span>
                <button onClick={() => updateQuantity(item.variant.id, item.quantity + 1)}>+</button>
                <button onClick={() => removeItem(item.variant.id)}>Remove</button>
              </div>
            </div>
          ))}

          <div style={{ margin: "1rem 0", display: "flex", gap: "0.5rem" }}>
            <input placeholder="Discount code" value={discountCode} onChange={(e) => setDiscountCode(e.target.value)} />
            <button onClick={applyDiscount}>Apply</button>
          </div>
          {discount && <p>Discount applied: {discount.type === "percentage" ? `${discount.value}%` : `$${discount.value}`} off</p>}

          <p style={{ fontSize: "1.2rem", fontWeight: "bold" }}>Total: ${finalTotal.toFixed(2)}</p>

          <h3>Delivery Details</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} />
            <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <input placeholder="Address" value={address} onChange={(e) => setAddress(e.target.value)} />
            <input placeholder="City" value={city} onChange={(e) => setCity(e.target.value)} />
            <input placeholder="ZIP code" value={zip} onChange={(e) => setZip(e.target.value)} />
          </div>

          {error && <p style={{ color: "red" }}>{error}</p>}
          <button onClick={placeOrder} disabled={!name || !phone || !address} style={{ marginTop: "1rem", padding: "0.75rem 2rem" }}>
            Place Order
          </button>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create OrderStatusPage**

Create `frontend/packages/store/src/pages/OrderStatusPage.tsx`:

```tsx
import { useState } from "react";
import { api } from "@openmarket/shared";
import type { Order } from "@openmarket/shared";

export function OrderStatusPage() {
  const [orderNumber, setOrderNumber] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  const lookup = async () => {
    setError("");
    try {
      // Search by listing and filtering client-side (simple approach for MVP)
      const orders = await api.orders.list();
      const found = orders.find((o) => o.order_number === orderNumber);
      if (!found) {
        setError("Order not found");
        return;
      }
      const full = await api.orders.get(found.id);
      setOrder(full);
    } catch {
      setError("Could not look up order");
    }
  };

  return (
    <div style={{ padding: "1rem", maxWidth: 600, margin: "0 auto" }}>
      <h2>Track Your Order</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          placeholder="Enter order number (e.g. ORD-...)"
          value={orderNumber}
          onChange={(e) => setOrderNumber(e.target.value)}
          style={{ flex: 1, padding: "0.5rem" }}
        />
        <button onClick={lookup}>Look Up</button>
      </div>
      {error && <p style={{ color: "red" }}>{error}</p>}
      {order && (
        <div style={{ border: "1px solid #ddd", padding: "1rem", borderRadius: "4px" }}>
          <h3>Order {order.order_number}</h3>
          <p><strong>Status:</strong> {order.fulfillment_status}</p>
          <p><strong>Total:</strong> ${order.total_price}</p>
          <p><strong>Placed:</strong> {new Date(order.created_at).toLocaleString()}</p>
          <h4>Items:</h4>
          <ul>
            {order.line_items.map((li) => (
              <li key={li.id}>{li.title} x{li.quantity} — ${li.price}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Install dependencies and verify build**

Run: `cd frontend && pnpm install && pnpm --filter @openmarket/store build`
Expected: Build succeeds, output in `frontend/packages/store/dist/`

- [ ] **Step 8: Commit**

```bash
git add frontend/packages/store/
git commit -m "feat: add web store frontend (shop, cart/checkout, order status)"
```

---

## Task 15: Admin Frontend

**Files:**
- Create: `frontend/packages/admin/package.json`
- Create: `frontend/packages/admin/tsconfig.json`
- Create: `frontend/packages/admin/vite.config.ts`
- Create: `frontend/packages/admin/index.html`
- Create: `frontend/packages/admin/src/main.tsx`
- Create: `frontend/packages/admin/src/App.tsx`
- Create: `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`
- Create: `frontend/packages/admin/src/pages/OrdersPage.tsx`

- [ ] **Step 1: Create admin package config**

Create `frontend/packages/admin/package.json`:

```json
{
  "name": "@openmarket/admin",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@openmarket/shared": "workspace:*",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^7.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.3",
    "vite": "^6.0.7"
  }
}
```

Create `frontend/packages/admin/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist"
  },
  "include": ["src"],
  "references": [{ "path": "../shared" }]
}
```

Create `frontend/packages/admin/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3002,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
```

Create `frontend/packages/admin/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenMarket Admin</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create main entry and App router**

Create `frontend/packages/admin/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
```

Create `frontend/packages/admin/src/App.tsx`:

```tsx
import { Routes, Route, Link, Navigate } from "react-router-dom";
import { ProductsInventoryPage } from "./pages/ProductsInventoryPage";
import { OrdersPage } from "./pages/OrdersPage";

export function App() {
  return (
    <div>
      <nav style={{ padding: "1rem", borderBottom: "1px solid #eee", display: "flex", gap: "1rem", alignItems: "center" }}>
        <strong style={{ fontSize: "1.2rem" }}>OpenMarket Admin</strong>
        <Link to="/products">Products & Inventory</Link>
        <Link to="/orders">Orders</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Navigate to="/products" replace />} />
        <Route path="/products" element={<ProductsInventoryPage />} />
        <Route path="/orders" element={<OrdersPage />} />
      </Routes>
    </div>
  );
}
```

- [ ] **Step 3: Create ProductsInventoryPage**

Create `frontend/packages/admin/src/pages/ProductsInventoryPage.tsx`:

```tsx
import { useEffect, useState, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductListItem, InventoryLevel } from "@openmarket/shared";

export function ProductsInventoryPage() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [inventory, setInventory] = useState<Record<number, InventoryLevel>>({});
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [expandedProduct, setExpandedProduct] = useState<Product | null>(null);

  const loadProducts = async () => {
    const prods = await api.products.list();
    setProducts(prods);
  };

  const loadInventory = async () => {
    const levels = await api.inventory.levels(1); // location_id=1 (single location)
    const map: Record<number, InventoryLevel> = {};
    for (const l of levels) map[l.inventory_item_id] = l;
    setInventory(map);
  };

  useEffect(() => {
    loadProducts();
    loadInventory();
  }, []);

  const handleInventoryUpdate = useCallback((update: { inventory_item_id: number; available: number; location_id: number }) => {
    setInventory((prev) => ({
      ...prev,
      [update.inventory_item_id]: { ...prev[update.inventory_item_id], available: update.available },
    }));
  }, []);

  useWebSocket(handleInventoryUpdate);

  const expand = async (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedProduct(null);
      return;
    }
    const product = await api.products.get(id);
    setExpandedId(id);
    setExpandedProduct(product);
  };

  const adjustStock = async (inventoryItemId: number, delta: number) => {
    await api.inventory.adjust({ inventory_item_id: inventoryItemId, location_id: 1, available_adjustment: delta });
    await loadInventory();
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Products & Inventory</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #333", textAlign: "left" }}>
            <th style={{ padding: "0.5rem" }}>Title</th>
            <th>Type</th>
            <th>Status</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <>
              <tr
                key={p.id}
                onClick={() => expand(p.id)}
                style={{ borderBottom: "1px solid #eee", cursor: "pointer", background: expandedId === p.id ? "#f9f9f9" : "transparent" }}
              >
                <td style={{ padding: "0.5rem" }}>{p.title}</td>
                <td>{p.product_type}</td>
                <td>{p.status}</td>
                <td>{p.tags.join(", ")}</td>
              </tr>
              {expandedId === p.id && expandedProduct && (
                <tr key={`${p.id}-detail`}>
                  <td colSpan={4} style={{ padding: "1rem", background: "#f5f5f5" }}>
                    <h4>Variants</h4>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead>
                        <tr style={{ textAlign: "left" }}>
                          <th>Variant</th>
                          <th>SKU</th>
                          <th>Barcode</th>
                          <th>Price</th>
                          <th>Stock</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {expandedProduct.variants.map((v) => {
                          const invItem = v.id; // variant_id maps to inventory_item via the relation
                          // We need to find the right inventory level — simplification: iterate inventory
                          const level = Object.values(inventory).find((l) => l.inventory_item_id === v.id) || null;
                          const stock = level?.available ?? "?";
                          const isLow = level && level.available <= level.low_stock_threshold;
                          return (
                            <tr key={v.id}>
                              <td>{v.title}</td>
                              <td>{v.sku}</td>
                              <td>{v.barcode}</td>
                              <td>${v.price}</td>
                              <td style={{ color: isLow ? "red" : "inherit", fontWeight: isLow ? "bold" : "normal" }}>
                                {stock} {isLow && "(LOW)"}
                              </td>
                              <td>
                                {level && (
                                  <>
                                    <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, -1); }}>-1</button>
                                    <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 1); }}>+1</button>
                                    <button onClick={(e) => { e.stopPropagation(); adjustStock(level.inventory_item_id, 10); }}>+10</button>
                                  </>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Create OrdersPage**

Create `frontend/packages/admin/src/pages/OrdersPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "@openmarket/shared";
import type { Order, OrderListItem } from "@openmarket/shared";

export function OrdersPage() {
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [tab, setTab] = useState<"unfulfilled" | "fulfilled">("unfulfilled");
  const [expandedOrder, setExpandedOrder] = useState<Order | null>(null);

  const loadOrders = async () => {
    const data = await api.orders.list({ fulfillment_status: tab });
    setOrders(data);
  };

  useEffect(() => {
    loadOrders();
  }, [tab]);

  const expandOrder = async (id: number) => {
    if (expandedOrder?.id === id) {
      setExpandedOrder(null);
      return;
    }
    const order = await api.orders.get(id);
    setExpandedOrder(order);
  };

  const fulfill = async (orderId: number) => {
    await api.fulfillments.create(orderId, { status: "delivered" });
    // Also update order fulfillment_status via the fulfillment update side-effect
    await loadOrders();
    setExpandedOrder(null);
  };

  return (
    <div style={{ padding: "1rem" }}>
      <h2>Orders</h2>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          onClick={() => setTab("unfulfilled")}
          style={{ fontWeight: tab === "unfulfilled" ? "bold" : "normal" }}
        >
          Unfulfilled
        </button>
        <button
          onClick={() => setTab("fulfilled")}
          style={{ fontWeight: tab === "fulfilled" ? "bold" : "normal" }}
        >
          Fulfilled
        </button>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #333", textAlign: "left" }}>
            <th style={{ padding: "0.5rem" }}>Order #</th>
            <th>Source</th>
            <th>Total</th>
            <th>Date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <>
              <tr
                key={o.id}
                onClick={() => expandOrder(o.id)}
                style={{ borderBottom: "1px solid #eee", cursor: "pointer" }}
              >
                <td style={{ padding: "0.5rem" }}>{o.order_number}</td>
                <td>{o.source}</td>
                <td>${o.total_price}</td>
                <td>{new Date(o.created_at).toLocaleDateString()}</td>
                <td>{o.fulfillment_status}</td>
              </tr>
              {expandedOrder?.id === o.id && (
                <tr key={`${o.id}-detail`}>
                  <td colSpan={5} style={{ padding: "1rem", background: "#f5f5f5" }}>
                    <h4>Line Items</h4>
                    <ul>
                      {expandedOrder.line_items.map((li) => (
                        <li key={li.id}>{li.title} x{li.quantity} @ ${li.price}</li>
                      ))}
                    </ul>
                    {expandedOrder.shipping_address && (
                      <>
                        <h4>Shipping Address</h4>
                        <p>
                          {expandedOrder.shipping_address.address1}, {expandedOrder.shipping_address.city} {expandedOrder.shipping_address.zip}
                        </p>
                      </>
                    )}
                    {expandedOrder.fulfillment_status === "unfulfilled" && (
                      <button onClick={() => fulfill(o.id)} style={{ marginTop: "0.5rem" }}>
                        Mark as Fulfilled
                      </button>
                    )}
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Install dependencies and verify build**

Run: `cd frontend && pnpm install && pnpm --filter @openmarket/admin build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/packages/admin/
git commit -m "feat: add admin dashboard (products/inventory, orders)"
```

---

## Task 16: POS Frontend

**Files:**
- Create: `frontend/packages/pos/package.json`
- Create: `frontend/packages/pos/tsconfig.json`
- Create: `frontend/packages/pos/vite.config.ts`
- Create: `frontend/packages/pos/index.html`
- Create: `frontend/packages/pos/src/main.tsx`
- Create: `frontend/packages/pos/src/App.tsx`
- Create: `frontend/packages/pos/src/pages/SalePage.tsx`

- [ ] **Step 1: Create POS package config**

Create `frontend/packages/pos/package.json`:

```json
{
  "name": "@openmarket/pos",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@openmarket/shared": "workspace:*",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.3",
    "vite": "^6.0.7"
  }
}
```

Create `frontend/packages/pos/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "outDir": "dist"
  },
  "include": ["src"],
  "references": [{ "path": "../shared" }]
}
```

Create `frontend/packages/pos/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3003,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        ws: true,
      },
    },
  },
});
```

Create `frontend/packages/pos/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenMarket POS</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 2: Create main entry and App**

Create `frontend/packages/pos/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Create `frontend/packages/pos/src/App.tsx`:

```tsx
import { SalePage } from "./pages/SalePage";

export function App() {
  return <SalePage />;
}
```

- [ ] **Step 3: Create SalePage**

Create `frontend/packages/pos/src/pages/SalePage.tsx`:

```tsx
import { useState, useRef, useEffect, useCallback } from "react";
import { api, useWebSocket } from "@openmarket/shared";
import type { Product, ProductVariant } from "@openmarket/shared";

interface SaleItem {
  variant: ProductVariant;
  productTitle: string;
  quantity: number;
}

export function SalePage() {
  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [saleItems, setSaleItems] = useState<SaleItem[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const barcodeRef = useRef<HTMLInputElement>(null);

  // Auto-focus barcode input
  useEffect(() => {
    barcodeRef.current?.focus();
  }, []);

  // Re-focus after sale completes
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => {
        setSuccess("");
        barcodeRef.current?.focus();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const handleInventoryUpdate = useCallback(() => {
    // POS could show low-stock warnings here
  }, []);

  useWebSocket(handleInventoryUpdate);

  const addByBarcode = async (barcode: string) => {
    setError("");
    try {
      // Search products and find variant by barcode
      const products = await api.products.list({ status: "active" });
      for (const p of products) {
        const full = await api.products.get(p.id);
        const variant = full.variants.find((v) => v.barcode === barcode);
        if (variant) {
          addToSale(full.title, variant);
          setBarcodeInput("");
          return;
        }
      }
      setError(`No product found with barcode: ${barcode}`);
    } catch {
      setError("Scan failed");
    }
  };

  const searchProducts = async (query: string) => {
    if (!query) {
      setSearchResults([]);
      return;
    }
    const products = await api.products.list({ status: "active", search: query });
    const full = await Promise.all(products.slice(0, 5).map((p) => api.products.get(p.id)));
    setSearchResults(full);
  };

  const addToSale = (productTitle: string, variant: ProductVariant) => {
    setSaleItems((prev) => {
      const existing = prev.find((i) => i.variant.id === variant.id);
      if (existing) {
        return prev.map((i) =>
          i.variant.id === variant.id ? { ...i, quantity: i.quantity + 1 } : i,
        );
      }
      return [...prev, { variant, productTitle, quantity: 1 }];
    });
    setSearchResults([]);
    setSearchInput("");
    barcodeRef.current?.focus();
  };

  const removeItem = (variantId: number) => {
    setSaleItems((prev) => prev.filter((i) => i.variant.id !== variantId));
  };

  const total = saleItems.reduce(
    (sum, item) => sum + parseFloat(item.variant.price) * item.quantity, 0,
  );

  const completeSale = async () => {
    setError("");
    try {
      await api.orders.create({
        source: "pos",
        line_items: saleItems.map((i) => ({ variant_id: i.variant.id, quantity: i.quantity })),
      });
      setSaleItems([]);
      setSuccess("Sale completed!");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleBarcodeKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && barcodeInput.trim()) {
      addByBarcode(barcodeInput.trim());
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* Left: input area */}
      <div style={{ flex: 1, padding: "1rem", borderRight: "1px solid #ddd" }}>
        <h2>POS</h2>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", fontWeight: "bold", marginBottom: "0.25rem" }}>Scan Barcode</label>
          <input
            ref={barcodeRef}
            value={barcodeInput}
            onChange={(e) => setBarcodeInput(e.target.value)}
            onKeyDown={handleBarcodeKeyDown}
            placeholder="Scan or type barcode..."
            style={{ width: "100%", padding: "0.75rem", fontSize: "1.1rem", boxSizing: "border-box" }}
          />
        </div>

        <div style={{ marginBottom: "1rem" }}>
          <label style={{ display: "block", fontWeight: "bold", marginBottom: "0.25rem" }}>Search Product</label>
          <input
            value={searchInput}
            onChange={(e) => { setSearchInput(e.target.value); searchProducts(e.target.value); }}
            placeholder="Type to search..."
            style={{ width: "100%", padding: "0.5rem", boxSizing: "border-box" }}
          />
          {searchResults.length > 0 && (
            <div style={{ border: "1px solid #ddd", maxHeight: 200, overflowY: "auto" }}>
              {searchResults.map((p) =>
                p.variants.map((v) => (
                  <div
                    key={v.id}
                    onClick={() => addToSale(p.title, v)}
                    style={{ padding: "0.5rem", cursor: "pointer", borderBottom: "1px solid #eee" }}
                  >
                    {p.title} — {v.title} (${v.price})
                  </div>
                )),
              )}
            </div>
          )}
        </div>

        {error && <p style={{ color: "red", fontWeight: "bold" }}>{error}</p>}
        {success && <p style={{ color: "green", fontWeight: "bold", fontSize: "1.2rem" }}>{success}</p>}
      </div>

      {/* Right: current sale */}
      <div style={{ width: 400, padding: "1rem", display: "flex", flexDirection: "column" }}>
        <h3>Current Sale</h3>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {saleItems.length === 0 ? (
            <p style={{ color: "#999" }}>No items scanned</p>
          ) : (
            saleItems.map((item) => (
              <div key={item.variant.id} style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid #eee" }}>
                <div>
                  <strong>{item.productTitle}</strong> — {item.variant.title}
                  <br />${item.variant.price} x {item.quantity}
                </div>
                <button onClick={() => removeItem(item.variant.id)} style={{ alignSelf: "center" }}>X</button>
              </div>
            ))
          )}
        </div>
        <div style={{ borderTop: "2px solid #333", paddingTop: "1rem" }}>
          <p style={{ fontSize: "1.5rem", fontWeight: "bold" }}>Total: ${total.toFixed(2)}</p>
          <button
            onClick={completeSale}
            disabled={saleItems.length === 0}
            style={{ width: "100%", padding: "1rem", fontSize: "1.2rem", background: "#4CAF50", color: "white", border: "none", cursor: "pointer" }}
          >
            Complete Sale
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Install dependencies and verify build**

Run: `cd frontend && pnpm install && pnpm --filter @openmarket/pos build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/packages/pos/
git commit -m "feat: add POS frontend"
```

---

## Task 17: Docker Compose & Nginx Deployment

**Files:**
- Create: `docker-compose.yml`
- Create: `nginx.conf`
- Create: `backend/Dockerfile`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `backend/seed.py`

- [ ] **Step 1: Create backend Dockerfile**

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: openmarket
      POSTGRES_USER: openmarket
      POSTGRES_PASSWORD: ${DB_PASSWORD:-openmarket}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openmarket"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build: ./backend
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+asyncpg://openmarket:${DB_PASSWORD:-openmarket}@db:5432/openmarket
    ports:
      - "8000:8000"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./frontend/packages/store/dist:/usr/share/nginx/html/store:ro
      - ./frontend/packages/admin/dist:/usr/share/nginx/html/admin:ro
      - ./frontend/packages/pos/dist:/usr/share/nginx/html/pos:ro
    depends_on:
      - api

volumes:
  pgdata:
```

- [ ] **Step 3: Create nginx.conf**

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    upstream api {
        server api:8000;
    }

    server {
        listen 80;

        # API and WebSocket proxy
        location /api/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Web Store
        location / {
            root /usr/share/nginx/html/store;
            try_files $uri $uri/ /index.html;
        }

        # Admin Dashboard
        location /admin/ {
            alias /usr/share/nginx/html/admin/;
            try_files $uri $uri/ /admin/index.html;
        }

        # POS
        location /pos/ {
            alias /usr/share/nginx/html/pos/;
            try_files $uri $uri/ /pos/index.html;
        }
    }
}
```

- [ ] **Step 4: Create .env.example**

Create `.env.example`:

```
DB_PASSWORD=openmarket
```

- [ ] **Step 5: Create .gitignore**

Create `.gitignore`:

```
# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Node
node_modules/
dist/

# IDE
.vscode/
.idea/

# Environment
.env

# Uploads
uploads/

# Superpowers
.superpowers/
```

- [ ] **Step 6: Create seed script**

Create `backend/seed.py`:

```python
"""Seed script to populate the database with sample data for development."""
import asyncio
from app.database import engine, async_session, Base
from app.models import *  # noqa


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Create location
        location = Location(name="Main Store", address="123 Market Street")
        db.add(location)
        await db.flush()

        # Create products
        products_data = [
            ("Whole Milk", "whole-milk", "dairy", [
                ("1L", "MILK-1L", "8801234000001", 2.99),
                ("2L", "MILK-2L", "8801234000002", 4.99),
            ]),
            ("White Bread", "white-bread", "bakery", [
                ("Standard", "BREAD-STD", "8801234000010", 1.99),
            ]),
            ("Organic Eggs", "organic-eggs", "dairy", [
                ("6 pack", "EGG-6", "8801234000020", 3.49),
                ("12 pack", "EGG-12", "8801234000021", 5.99),
            ]),
            ("Coca-Cola", "coca-cola", "beverages", [
                ("330ml Can", "COKE-330", "8801234000030", 1.29),
                ("500ml Bottle", "COKE-500", "8801234000031", 1.79),
                ("2L Bottle", "COKE-2L", "8801234000032", 2.99),
            ]),
            ("Banana", "banana", "fruits", [
                ("Per kg", "BANANA-KG", "8801234000040", 1.49),
            ]),
        ]

        for title, handle, ptype, variants_data in products_data:
            product = Product(title=title, handle=handle, product_type=ptype, status="active", tags=[ptype])
            for vtitle, sku, barcode, price in variants_data:
                variant = ProductVariant(title=vtitle, sku=sku, barcode=barcode, price=price)
                inv_item = InventoryItem()
                inv_item.levels.append(InventoryLevel(location_id=location.id, available=100, low_stock_threshold=10))
                variant.inventory_item = inv_item
                product.variants.append(variant)
            db.add(product)

        # Create collections
        dairy = Collection(title="Dairy", handle="dairy", collection_type="manual")
        beverages = Collection(title="Beverages", handle="beverages", collection_type="manual")
        db.add_all([dairy, beverages])

        await db.commit()
        print("Seed data created successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 7: Verify Docker Compose works**

Run: `docker compose up --build -d`
Expected: All three services start. API reachable at `http://localhost:8000/api/health`.

- [ ] **Step 8: Run seed script**

Run: `cd backend && python seed.py`
Expected: "Seed data created successfully!"

- [ ] **Step 9: Run full backend test suite one final time**

Run: `cd backend && python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add docker-compose.yml nginx.conf backend/Dockerfile backend/seed.py .env.example .gitignore
git commit -m "feat: add Docker Compose deployment, Nginx config, and seed data"
```
