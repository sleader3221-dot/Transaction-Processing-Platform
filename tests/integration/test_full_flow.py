import io
import pytest
import pytest_asyncio

VALID_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-INT-1,ACC-INT-1,CREDIT,1500.00,USD,2026-09-01T10:00:00Z
TXN-INT-2,ACC-INT-1,DEBIT,250.00,USD,2026-09-01T10:01:00Z
TXN-INT-3,ACC-INT-2,CREDIT,700.00,USD,2026-09-01T10:02:00Z
"""


@pytest.mark.asyncio
async def test_full_import_flow(client, api_key):
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    assert upload.status_code == 202
    import_id = upload.json()["import_id"]

    import asyncio
    for _ in range(30):
        status = await client.get(
            f"/api/v1/imports/{import_id}",
            headers={"X-API-Key": api_key},
        )
        if status.json()["status"] == "COMPLETED":
            break
        await asyncio.sleep(0.5)
    else:
        pytest.fail("Import did not complete in time")

    final_status = status.json()
    assert final_status["status"] == "COMPLETED"
    assert final_status["successful_rows"] == 3
    assert final_status["failed_rows"] == 0

    tx_list = await client.get(
        f"/api/v1/transactions?account_id=ACC-INT-1",
        headers={"X-API-Key": api_key},
    )
    assert tx_list.status_code == 200
    assert tx_list.json()["total"] == 2

    summary = await client.get(
        "/api/v1/accounts/ACC-INT-1/summary",
        headers={"X-API-Key": api_key},
    )
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_credits"] == 1500.0
    assert data["total_debits"] == 250.0
    assert data["balance"] == 1250.0


@pytest.mark.asyncio
async def test_import_with_errors(client, api_key):
    bad_csv = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-BAD-1,ACC-BAD,CREDIT,100.00,USD,2026-09-01T10:00:00Z
TXN-BAD-2,,DEBIT,50.00,USD,2026-09-01T10:01:00Z
TXN-BAD-3,ACC-BAD,INVALID,100.00,USD,2026-09-01T10:02:00Z
"""
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    import_id = upload.json()["import_id"]

    import asyncio
    for _ in range(30):
        status = await client.get(
            f"/api/v1/imports/{import_id}",
            headers={"X-API-Key": api_key},
        )
        if status.json()["status"] == "COMPLETED":
            break
        await asyncio.sleep(0.5)

    final = status.json()
    assert final["successful_rows"] == 1
    assert final["failed_rows"] == 2

    errors = await client.get(
        f"/api/v1/imports/{import_id}/errors",
        headers={"X-API-Key": api_key},
    )
    assert errors.status_code == 200
    assert errors.json()["total"] == 2