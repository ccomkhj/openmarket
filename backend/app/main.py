from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.api.products import router as products_router


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
