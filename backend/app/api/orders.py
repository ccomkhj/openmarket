from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_any_staff
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate, OrderOut, OrderListOut
from app.services.order import create_order
from app.services.weighed import (
    WeightMissingError,
    WeightOutOfRangeError,
    PricingTypeMismatchError,
    QuantityOnWeighedError,  # new
)

router = APIRouter(
    prefix="/api",
    tags=["orders"],
    dependencies=[Depends(require_any_staff)],
)


@router.post("/orders", response_model=OrderOut, status_code=201)
async def create(body: OrderCreate, db: AsyncSession = Depends(get_db)):
    try:
        order = await create_order(
            db=db,
            source=body.source,
            line_items_data=[li.model_dump() for li in body.line_items],
            customer_id=body.customer_id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            shipping_address=body.shipping_address,
            shipping_method_id=body.shipping_method_id,
        )
    except (
        WeightMissingError,
        WeightOutOfRangeError,
        PricingTypeMismatchError,
        QuantityOnWeighedError,
    ) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.get("/orders", response_model=list[OrderListOut])
async def list_orders(
    source: str | None = None,
    fulfillment_status: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
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


@router.get("/orders/unfulfilled-count")
async def unfulfilled_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(func.count(Order.id)).where(Order.fulfillment_status == "unfulfilled")
    )
    return {"count": int(result.scalar() or 0)}


@router.get("/orders/lookup", response_model=OrderOut)
async def lookup_order(order_number: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .where(Order.order_number == order_number)
        .options(selectinload(Order.line_items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


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
    await db.refresh(order, ["line_items"])
    return order
