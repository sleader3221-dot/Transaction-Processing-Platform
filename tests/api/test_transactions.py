import pytest
import pytest_asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from app.models.transaction import Transaction


@pytest_asyncio.fixture
async def populated_db(db_session):
    tx1 = Transaction(
        id=uuid.uuid4(), transaction_id="TXN-API-1", account_id="ACC-API-1",
        type="CREDIT", amount=Decimal("1000.00"), currency="USD",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    tx2 = Transaction(
        id=uuid.uuid4(), transaction_id="TXN-API-2", account_id="ACC-API-1",
        type="DEBIT", amount=Decimal("200.00"), currency="USD",
        timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc)
    )
    tx3 = Transaction(
        id=uuid.uuid4(), transaction_id="TXN-API-3", account_id="ACC-API-2",
        type="CREDIT", amount=Decimal("500.00"), currency="EUR",
        timestamp=datetime(2026, 1, 3, tzinfo=timezone.utc)
    )
    db_session.add_all([tx1, tx2, tx3])
    await db_session.commit()
    return [tx1, tx2, tx3]


@pytest.mark.asyncio
async def test_get_transaction(client, api_key, populated_db):
    tx = populated_db[0]
    r = await client.get(
        f"/api/v1/transactions/{tx.transaction_id}",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["transaction_id"] == tx.transaction_id
    assert Decimal(data["amount"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_get_transaction_not_found(client, api_key):
    r = await client.get(
        "/api/v1/transactions/NONEXISTENT",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_transactions(client, api_key, populated_db):
    r = await client.get(
        "/api/v1/transactions?account_id=ACC-API-1",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_transactions_filter_type(client, api_key, populated_db):
    r = await client.get(
        "/api/v1/transactions?account_id=ACC-API-1&type=CREDIT",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["type"] == "CREDIT"


@pytest.mark.asyncio
async def test_list_transactions_filter_currency(client, api_key, populated_db):
    r = await client.get(
        "/api/v1/transactions?currency=EUR",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_transactions_pagination(client, api_key, populated_db):
    r = await client.get(
        "/api/v1/transactions?page=1&limit=1",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["limit"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_list_transactions_sorting(client, api_key, populated_db):
    r = await client.get(
        "/api/v1/transactions?sort_by=amount&sort_order=desc",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 200
    data = r.json()
    amounts = [float(item["amount"]) for item in data["items"]]
    assert amounts == sorted(amounts, reverse=True)
