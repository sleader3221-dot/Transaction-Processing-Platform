import io
import pytest
import pytest_asyncio

VALID_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-001,ACC-1001,CREDIT,1500.00,USD,2026-09-01T10:00:00Z
TXN-002,ACC-1001,DEBIT,250.00,USD,2026-09-01T10:01:00Z
"""


@pytest.mark.asyncio
async def test_upload_csv(client, api_key):
    response = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("transactions.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    assert response.status_code == 202
    data = response.json()
    assert "import_id" in data
    assert data["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_upload_non_csv_rejected(client, api_key):
    response = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_import_status(client, api_key):
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("t.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    import_id = upload.json()["import_id"]

    status = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    assert status.status_code == 200
    data = status.json()
    assert data["import_id"] == import_id
    assert data["status"] in ("QUEUED", "PROCESSING", "COMPLETED", "FAILED")


@pytest.mark.asyncio
async def test_import_not_found(client, api_key):
    r = await client.get(
        "/api/v1/imports/does-not-exist",
        headers={"X-API-Key": api_key},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_no_auth_rejected(client):
    r = await client.post(
        "/api/v1/imports",
        files={"file": ("t.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    assert r.status_code == 401