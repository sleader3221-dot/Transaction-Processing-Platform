import asyncio
import io
import hashlib
import secrets
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import get_db
from app.models.api_key import ApiKey
from app.core.id_gen import generate_id

DUPLICATE_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-DUPE-1,ACC-9999,CREDIT,100.00,USD,2026-09-01T10:00:00Z
TXN-DUPE-2,ACC-9999,DEBIT,50.00,USD,2026-09-01T10:01:00Z
"""


@pytest.mark.asyncio
async def test_concurrent_duplicate_imports(db_session):
    import fakeredis.aioredis as fakeredis
    from app.redis_client.client import get_redis

    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db_session.add(ApiKey(id=generate_id(), client_id="conc-test",
                          key_hash=key_hash, is_active=True))
    await db_session.commit()

    async def override_db():
        yield db_session

    async def override_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    async def upload():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            return await c.post(
                "/api/v1/imports",
                headers={"X-API-Key": raw_key},
                files={"file": ("t.csv", io.BytesIO(DUPLICATE_CSV), "text/csv")},
            )

    responses = await asyncio.gather(*[upload() for _ in range(5)])
    assert all(r.status_code == 202 for r in responses)

    app.dependency_overrides.clear()