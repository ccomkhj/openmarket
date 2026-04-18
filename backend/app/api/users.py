from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_owner
from app.models import User
from app.schemas.auth import UserCreate, UserOut
from app.services.password import hash_password, hash_pin

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(require_owner)],
)


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        active=u.active,
        created_at=u.created_at.isoformat() if u.created_at else None,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.role, User.full_name))
    return [_to_out(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(req: UserCreate, db: AsyncSession = Depends(get_db)):
    if req.role not in ("owner", "manager", "cashier"):
        raise HTTPException(status_code=400, detail="role must be owner/manager/cashier")

    if req.role == "cashier":
        if not req.pin:
            raise HTTPException(status_code=400, detail="cashier requires pin")
        u = User(
            email=None,
            password_hash=None,
            pin_hash=hash_pin(req.pin),
            full_name=req.full_name,
            role="cashier",
        )
    else:
        if not req.email or not req.password:
            raise HTTPException(status_code=400, detail=f"{req.role} requires email and password")
        u = User(
            email=req.email,
            password_hash=hash_password(req.password),
            full_name=req.full_name,
            role=req.role,
        )

    db.add(u)
    await db.commit()
    await db.refresh(u)
    return _to_out(u)


@router.patch("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(user_id: int, db: AsyncSession = Depends(get_db)):
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    u.active = False
    await db.commit()
    return _to_out(u)
