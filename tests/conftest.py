import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.base import Base
from app.db import database as db_module
from app.config import get_settings

settings = get_settings()

TEST_DB_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine, db_session):
    from app.db.database import get_db
    from app.redis_client.client import get_redis
    import fakeredis.aioredis as fakeredis

    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_key(db_session) -> str:
    import hashlib, secrets
    from app.models.api_key import ApiKey
    from app.core.id_gen import generate_id

    raw = secrets.token_urlsafe(32)
    db_session.add(ApiKey(
        id=generate_id(), client_id="test-client",
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        is_active=True,
    ))
    await db_session.commit()
    return raw