import ipaddress
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.config import settings
from app.models import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, PosLoginRequest, PosLoginResponse,
    SetupRequest, MfaEnrollResponse, MfaVerifyRequest, MeResponse,
)
from app.services.audit import log_event
from app.services.mfa import new_totp_secret, totp_uri, verify_totp
from app.services.password import (
    hash_password, verify_password, verify_pin,
    check_password_not_breached,
)
from app.services.rate_limit import is_locked, record_attempt
from app.services.session import create_session, revoke_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

ADMIN_TTL_MIN = 8 * 60
POS_TTL_MIN = 14 * 60


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _ip_is_lan(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    cidrs = [c.strip() for c in settings.lan_ip_cidrs.split(",") if c.strip()]
    return any(addr in ipaddress.ip_network(c) for c in cidrs)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.admin_session_absolute_max_hours * 3600,
        path="/",
    )


@router.post("/setup", response_model=LoginResponse)
async def setup(req: SetupRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="setup already completed")
    await check_password_not_breached(req.password)
    owner = User(
        email=req.email,
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role="owner",
    )
    db.add(owner)
    await db.flush()
    sess = await create_session(
        db, user_id=owner.id, ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=ADMIN_TTL_MIN,
    )
    await log_event(db, event_type="auth.setup", actor_user_id=owner.id, ip=_client_ip(request), payload={"email": req.email})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return LoginResponse(user_id=owner.id, role="owner")


@router.get("/cashiers", response_model=list[PosLoginResponse])
async def list_cashiers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .where(User.role == "cashier", User.active.is_(True))
        .order_by(User.full_name)
    )
    return [PosLoginResponse(user_id=u.id, full_name=u.full_name) for u in result.scalars().all()]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    key = f"pw:{ip}"
    if await is_locked(db, key=key, window_seconds=15 * 60, max_failures=5):
        raise HTTPException(status_code=429, detail="too many attempts, try later")

    result = await db.execute(select(User).where(User.email == req.email, User.active.is_(True)))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        await record_attempt(db, key=key, succeeded=False)
        await log_event(db, event_type="auth.login.failed", actor_user_id=None, ip=ip, payload={"email": req.email})
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    if user.mfa_totp_secret:
        if not req.totp_code:
            return LoginResponse(user_id=user.id, role=user.role, mfa_required=True)
        if not verify_totp(secret=user.mfa_totp_secret, code=req.totp_code):
            await record_attempt(db, key=key, succeeded=False)
            await log_event(db, event_type="auth.login.mfa_failed", actor_user_id=user.id, ip=ip, payload={})
            await db.commit()
            raise HTTPException(status_code=401, detail="invalid MFA code")

    await record_attempt(db, key=key, succeeded=True)
    sess = await create_session(
        db, user_id=user.id, ip=ip,
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=ADMIN_TTL_MIN,
        mfa_method="totp" if user.mfa_totp_secret else None,
    )
    user.last_login_at = datetime.now(timezone.utc)
    await log_event(db, event_type="auth.login.success", actor_user_id=user.id, ip=ip, payload={})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return LoginResponse(user_id=user.id, role=user.role)


@router.post("/pos-login", response_model=PosLoginResponse)
async def pos_login(req: PosLoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    ip = _client_ip(request)
    if not _ip_is_lan(ip):
        await log_event(db, event_type="auth.pos_login.non_lan", actor_user_id=None, ip=ip, payload={"user_id": req.user_id})
        await db.commit()
        raise HTTPException(status_code=403, detail="POS login only from LAN")

    key = f"pin:{req.user_id}"
    if await is_locked(db, key=key, window_seconds=5 * 60, max_failures=5):
        raise HTTPException(status_code=429, detail="PIN locked, try later")

    user = await db.get(User, req.user_id)
    if not user or user.role != "cashier" or not user.pin_hash or not user.active:
        await record_attempt(db, key=key, succeeded=False)
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    if not verify_pin(req.pin, user.pin_hash):
        await record_attempt(db, key=key, succeeded=False)
        await log_event(db, event_type="auth.pos_login.failed", actor_user_id=user.id, ip=ip, payload={})
        await db.commit()
        raise HTTPException(status_code=401, detail="invalid credentials")

    await record_attempt(db, key=key, succeeded=True)
    sess = await create_session(
        db, user_id=user.id, ip=ip,
        user_agent=request.headers.get("user-agent"),
        ttl_minutes=POS_TTL_MIN,
    )
    user.last_login_at = datetime.now(timezone.utc)
    await log_event(db, event_type="auth.pos_login.success", actor_user_id=user.id, ip=ip, payload={})
    await db.commit()
    _set_session_cookie(response, sess.id)
    return PosLoginResponse(user_id=user.id, full_name=user.full_name)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        await revoke_session(db, sid)
        await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role)


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
async def mfa_enroll(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.mfa_totp_secret:
        raise HTTPException(status_code=400, detail="MFA already enrolled")
    secret = new_totp_secret()
    user.mfa_totp_secret = secret
    await log_event(db, event_type="auth.mfa.enrolled", actor_user_id=user.id, ip=None, payload={})
    await db.commit()
    return MfaEnrollResponse(secret=secret, uri=totp_uri(secret=secret, user_email=user.email or ""))


@router.post("/mfa/verify")
async def mfa_verify(req: MfaVerifyRequest, user: User = Depends(get_current_user)):
    if not user.mfa_totp_secret:
        raise HTTPException(status_code=400, detail="MFA not enrolled")
    if not verify_totp(secret=user.mfa_totp_secret, code=req.code):
        raise HTTPException(status_code=401, detail="invalid code")
    return {"ok": True}
