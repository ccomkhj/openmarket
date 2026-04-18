from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_any_staff
from app.models.order import Return
from app.schemas.returns import ReturnCreate, ReturnOut
from app.services.returns import create_return

router = APIRouter(
    prefix="/api",
    tags=["returns"],
    dependencies=[Depends(require_any_staff)],
)


@router.post("/returns", response_model=ReturnOut, status_code=201)
async def create(body: ReturnCreate, db: AsyncSession = Depends(get_db)):
    try:
        return_record = await create_return(
            db=db,
            order_id=body.order_id,
            return_items=[item.model_dump() for item in body.items],
            reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return return_record


@router.get("/orders/{order_id}/returns", response_model=list[ReturnOut])
async def list_returns(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Return)
        .where(Return.order_id == order_id)
        .options(selectinload(Return.items))
        .order_by(Return.created_at.desc())
    )
    return result.scalars().all()
