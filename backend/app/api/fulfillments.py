from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.models.order import Fulfillment, Order
from app.schemas.fulfillment import FulfillmentCreate, FulfillmentUpdate, FulfillmentOut

router = APIRouter(
    prefix="/api",
    tags=["fulfillments"],
    dependencies=[Depends(require_any_staff)],
)


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
