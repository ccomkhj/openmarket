import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db, require_any_staff
from app.models.auth import User
from app.models.customer import Customer
from app.models.parked_sale import ParkedSale
from app.schemas.parked_sale import ParkedItem, ParkedSaleCreate, ParkedSaleOut

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["parked-sales"],
    dependencies=[Depends(require_any_staff)],
)


def _to_out(ps: ParkedSale) -> ParkedSaleOut:
    items: list[ParkedItem] = []
    item_count = 0
    for raw in (ps.items or []):
        try:
            it = ParkedItem(**raw)
        except ValidationError as exc:
            logger.warning("parked_sale %s: bad item dropped: %s", ps.id, exc)
            continue
        items.append(it)
        item_count += int(it.quantity or 0)
    name = None
    if ps.customer is not None:
        name = f"{ps.customer.first_name or ''} {ps.customer.last_name or ''}".strip() or None
    return ParkedSaleOut(
        id=ps.id,
        cashier_user_id=ps.cashier_user_id,
        customer_id=ps.customer_id,
        customer_name=name,
        items=items,
        note=ps.note or "",
        created_at=ps.created_at,
        item_count=item_count,
    )


@router.get("/parked-sales", response_model=list[ParkedSaleOut])
async def list_parked_sales(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List parked sales visible to the current cashier.

    Cashiers see only their own; managers/owners see everyone's.
    """
    query = select(ParkedSale).options(selectinload(ParkedSale.customer))
    if user.role == "cashier":
        query = query.where(ParkedSale.cashier_user_id == user.id)
    query = query.order_by(ParkedSale.created_at.desc())
    result = await db.execute(query)
    return [_to_out(ps) for ps in result.scalars().all()]


@router.post("/parked-sales", response_model=ParkedSaleOut, status_code=201)
async def create_parked_sale(
    body: ParkedSaleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.items:
        raise HTTPException(status_code=400, detail="No items to park")
    if body.customer_id is not None:
        c = await db.scalar(select(Customer).where(Customer.id == body.customer_id))
        if c is None:
            raise HTTPException(status_code=404, detail="Customer not found")
    ps = ParkedSale(
        cashier_user_id=user.id,
        customer_id=body.customer_id,
        items=[i.model_dump() for i in body.items],
        note=body.note,
    )
    db.add(ps)
    await db.commit()
    await db.refresh(ps, ["customer"])
    return _to_out(ps)


@router.get("/parked-sales/{ps_id}", response_model=ParkedSaleOut)
async def get_parked_sale(
    ps_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ps = await db.scalar(
        select(ParkedSale)
        .where(ParkedSale.id == ps_id)
        .options(selectinload(ParkedSale.customer))
    )
    if ps is None:
        raise HTTPException(status_code=404, detail="Parked sale not found")
    if user.role == "cashier" and ps.cashier_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your parked sale")
    return _to_out(ps)


@router.delete("/parked-sales/{ps_id}", status_code=204)
async def delete_parked_sale(
    ps_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ps = await db.scalar(select(ParkedSale).where(ParkedSale.id == ps_id))
    if ps is None:
        raise HTTPException(status_code=404, detail="Parked sale not found")
    if user.role == "cashier" and ps.cashier_user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your parked sale")
    await db.delete(ps)
    await db.commit()
