import logging
import time
from contextlib import asynccontextmanager

from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.api.deps import get_db

from app.database import engine, Base, async_session
from app.config import settings
from app.services.session import get_active_session
from app.api.products import router as products_router
from app.api.collections import router as collections_router
from app.api.inventory import router as inventory_router
from app.api.customers import router as customers_router
from app.api.orders import router as orders_router
from app.api.fulfillments import router as fulfillments_router
from app.api.discounts import router as discounts_router
from app.api.analytics import router as analytics_router
from app.api.tax_shipping import router as tax_shipping_router
from app.api.returns import router as returns_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.receipts import router as receipts_router
from app.api.payment import router as payment_router
from app.api.kassenbuch import router as kassenbuch_router
from app.api.storno import router as storno_router
from app.api.reports import router as reports_router
from app.ws.manager import manager
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("openmarket")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(
            "%s %s %s %sms",
            request.method,
            request.url.path,
            response.status_code,
            duration,
        )
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.fiskaly_api_key:
        async with async_session() as db:
            async with httpx.AsyncClient(timeout=15) as http_client:
                fc = FiscalClient(
                    api_key=settings.fiskaly_api_key,
                    api_secret=settings.fiskaly_api_secret,
                    tss_id=settings.fiskaly_tss_id,
                    base_url=settings.fiskaly_base_url,
                    http=http_client,
                )
                try:
                    n = await FiscalService(client=fc, db=db).retry_pending_signatures()
                    if n:
                        logger.info("fiscal: re-signed %d pending transactions on startup", n)
                except Exception as e:
                    logger.warning("fiscal startup retry failed: %s", e)
    yield


app = FastAPI(title="OpenMarket API", lifespan=lifespan)

_allowed = [o.strip() for o in settings.allowed_cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Forwarded-For"],
)

app.add_middleware(LoggingMiddleware)

app.include_router(products_router)
app.include_router(collections_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(fulfillments_router)
app.include_router(discounts_router)
app.include_router(analytics_router)
app.include_router(tax_shipping_router)
app.include_router(returns_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(receipts_router)
app.include_router(payment_router)
app.include_router(kassenbuch_router)
app.include_router(storno_router)
app.include_router(reports_router)


upload_path = Path(settings.upload_dir)
upload_path.mkdir(exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(upload_path)), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/ws")
async def websocket_http_probe(request: Request, db: AsyncSession = Depends(get_db)):
    # Guard the ws path at the HTTP layer so unauthenticated upgrade attempts
    # get a clean 401 instead of being silently handed to the ws handler.
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        return Response(status_code=401)
    sess = await get_active_session(db, sid)
    if not sess:
        return Response(status_code=401)
    # Authed HTTP GET (no real ws handshake) — tell the client to upgrade.
    return Response(status_code=426)


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    sid = websocket.cookies.get(settings.session_cookie_name)
    if not sid:
        await websocket.close(code=1008)
        return
    async with async_session() as db:
        sess = await get_active_session(db, sid)
    if not sess:
        await websocket.close(code=1008)
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
