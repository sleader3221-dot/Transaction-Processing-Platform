from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.config import get_settings

settings = get_settings()

_database_url = make_url(settings.DATABASE_URL)
_query = dict(_database_url.query)
_ssl_required = _query.pop("sslmode", None) == "require"
_query.pop("channel_binding", None)
_db_url = _database_url.set(
    drivername="postgresql+asyncpg",
    query=_query,
).render_as_string(hide_password=False)

_engine_options = {
    "connect_args": {
        "statement_cache_size": 0,
        **({"ssl": True} if _ssl_required else {}),
    },
    "pool_pre_ping": True,
    "echo": settings.APP_ENV == "development",
}
if settings.TESTING:
    _engine_options["poolclass"] = NullPool
else:
    _engine_options.update(pool_size=20, max_overflow=5)

engine = create_async_engine(_db_url, **_engine_options)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
