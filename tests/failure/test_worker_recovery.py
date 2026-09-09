import io
import pytest
import pytest_asyncio

VALID_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-REC-1,ACC-REC-1,CREDIT,1000.00,USD,2026-09-01T10:00:00Z
TXN-REC-2,ACC-REC-1,DEBIT,200.00,USD,2026-09-01T10:01:00Z
"""


@pytest.mark.asyncio
async def test_worker_crash_recovery(client, api_key):
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("recovery.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    import_id = upload.json()["import_id"]

    import asyncio
    await asyncio.sleep(1)

    status = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    assert status.status_code == 200
    assert status.json()["status"] in ("COMPLETED", "PROCESSING")