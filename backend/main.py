from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.memory.redis_store import get_redis_client

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = await get_redis_client()
    await client.ping()
    log.info("redis_connected")
    yield
    await client.aclose()
    log.info("redis_disconnected")


app = FastAPI(title="Agentic Code Execution Sandbox", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
