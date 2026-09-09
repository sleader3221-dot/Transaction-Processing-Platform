import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import fakeredis.aioredis as fakeredis

from app.main import app
from app.db.database import get_db
from app.redis_client.client import get_redis
from app.models.transaction import Transaction
from app.core.id_gen import generate_id
from decimal import Decimal
from datetime import datetime, timezone


@pytest_asyncio.fixture
async def account_db(db_session):
    txs = [
        Transaction(
            id=generate_id(), transaction_id=f"TXN-SUM-{i}", account_id="ACC-SUM-1",
            type="CREDIT", amount=Decimal("1000.00"), currency="USD",
            timestamp=datetime(2026, 1, i, tzinfo=timezone.utc)
        ) for i in range(1, 6)
    ] + [
        Transaction(
            id=generate_id(), transaction_id=f"TXN-SUM-D-{i}", account_id="ACC-SUM-1",
            type="DEBIT", amount=Decimal("200.00"), currency="USD",
            timestamp=datetime(2026, 2, i, tzinfo=timezone.utc)
        ) for i in range(1, 4)
    ]
    db_session.add_all(txs)
    await db_session.commit()
    return txs


@pytest.mark.asyncio
async def test_account_summary(client, api_key, account_db):
    r = await client.get(
        "/api/v1/accounts/ACC-SUM-1/summary",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["account_id"] == "ACC-SUM-1"
    assert data["total_credits"] == 5000.0
    assert data["total_debits"] == 600.0
    assert data["balance"] == 4400.0
    assert data["transaction_count"] == 8


@pytest.mark.asyncio
async def test_account_summary_not_found(client, api_key):
    r = await client.get(
        "/api/v1/accounts/NONEXISTENT/summary",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_account_summary_caching(client, api_key, account_db):
    r1 = await client.get(
        "/api/v1/accounts/ACC-SUM-1/summary",
        headers={"X-API-Key": api_key},
    )
    r2 = await client.get(
        "/api/v1/accounts/ACC-SUM-1/summary",
        headers={"X-API-Key": api_key},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == r2.json()