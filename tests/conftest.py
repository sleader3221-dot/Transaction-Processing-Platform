import asyncio
import hashlib
import os
import secrets

os.environ["TESTING"] = "true"

import fakeredis.aioredis as fakeredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db.base import Base
from app.main import app


settings = get_settings()
TEST_DB_URL = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)
TEST_DB_URL += "?prepared_statement_cache_size=0"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.redis_client.client import get_redis

    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    session_factory = async_sessionmaker(
        db_session.bind, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()


@pytest_asyncio.fixture
async def api_key(db_session) -> str:
    from app.core.id_gen import generate_id
    from app.models.api_key import ApiKey

    raw_key = f"test-{secrets.token_hex(16)}"
    db_session.add(
        ApiKey(
            id=generate_id(),
            client_id="test-client",
            key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
            is_active=True,
        )
    )
    await db_session.commit()
    return raw_key
