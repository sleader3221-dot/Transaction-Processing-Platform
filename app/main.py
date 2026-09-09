import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging_config import setup_logging
from app.db.database import init_db
from app.redis_client.client import get_redis
from app.redis_client.rate_limiter import SlidingWindowRateLimiter
from app.api import health
from app.api.v1 import imports, transactions, accounts

setup_logging()
logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("application_started", env=settings.APP_ENV)
    yield
    logger.info("application_stopped")


app = FastAPI(
    title="Transaction Processing Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    if not request.url.path.startswith("/health"):
        redis = await get_redis()
        limiter = SlidingWindowRateLimiter(
            redis, settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW
        )
        client_id = request.headers.get("X-API-Key") or (request.client.host if request.client else "unknown")
        allowed, count = await limiter.is_allowed(client_id)

        if not allowed:
            return Response(
                content='{"detail":"Too Many Requests"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW),
                         "X-Request-ID": request_id},
            )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health.router)
app.include_router(imports.router, prefix="/api/v1", tags=["Imports"])
app.include_router(transactions.router, prefix="/api/v1", tags=["Transactions"])
app.include_router(accounts.router, prefix="/api/v1", tags=["Accounts"])