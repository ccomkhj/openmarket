from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.products import router as products_router
from app.api.collections import router as collections_router
from app.api.inventory import router as inventory_router
from app.api.customers import router as customers_router
from app.api.orders import router as orders_router
from app.api.fulfillments import router as fulfillments_router
from app.api.discounts import router as discounts_router
from app.api.analytics import router as analytics_router
from app.ws.manager import manager


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

app.include_router(products_router)
app.include_router(collections_router)
app.include_router(inventory_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(fulfillments_router)
app.include_router(discounts_router)
app.include_router(analytics_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
