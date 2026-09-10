"""
Concurrency tests for duplicate transaction prevention.
Verifies DB-level uniqueness when same data arrives from multiple sources.
"""
import asyncio
import io
import uuid
import pytest
from decimal import Decimal

from app.workers.import_worker import _process_import
from app.models.transaction import Transaction
from sqlalchemy import select, func

DUPLICATE_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-CONC-1,ACC-CONC,CREDIT,100.00,USD,2026-09-01T10:00:00Z
TXN-CONC-2,ACC-CONC,DEBIT,50.00,USD,2026-09-01T10:01:00Z
"""


@pytest.mark.asyncio
async def test_concurrent_duplicate_imports_db_uniqueness(client, api_key, db_session):
    """
    Upload the same CSV 5 times concurrently.
    Process all 5 imports.
    DB must contain exactly 2 transactions (not 10).
    """
    async def upload():
        return await client.post(
            "/api/v1/imports",
            headers={"X-API-Key": api_key},
            files={"file": ("dup.csv", io.BytesIO(DUPLICATE_CSV), "text/csv")},
        )

    # 5 concurrent uploads
    responses = await asyncio.gather(*[upload() for _ in range(5)])
    assert all(r.status_code == 202 for r in responses)
    import_ids = [r.json()["import_id"] for r in responses]

    # Process all 5 concurrently (real-world scenario)
    await asyncio.gather(*[_process_import(imp_id) for imp_id in import_ids])

    # KEY ASSERTION: DB must have exactly 2 unique transactions
    count = (await db_session.execute(
        select(func.count(Transaction.id))
        .where(Transaction.account_id == "ACC-CONC")
    )).scalar_one()
    assert count == 2, f"Expected 2 unique transactions, got {count}"


@pytest.mark.asyncio
async def test_in_file_duplicate_recorded_as_error(client, api_key):
    """Duplicate transaction_id within a single file → error recorded."""
    csv_with_dup = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-INDUP-1,ACC-INDUP,CREDIT,100.00,USD,2026-09-01T10:00:00Z
TXN-INDUP-1,ACC-INDUP,CREDIT,100.00,USD,2026-09-01T10:01:00Z
TXN-INDUP-2,ACC-INDUP,DEBIT,50.00,USD,2026-09-01T10:02:00Z
"""
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("indup.csv", io.BytesIO(csv_with_dup), "text/csv")},
    )
    import_id = upload.json()["import_id"]
    await _process_import(import_id)

    status = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    data = status.json()
    # Row 1: OK, Row 2: duplicate error, Row 3: OK
    assert data["successful_rows"] == 2
    assert data["failed_rows"] == 1

    errors = await client.get(
        f"/api/v1/imports/{import_id}/errors",
        headers={"X-API-Key": api_key},
    )
    assert errors.json()["total"] == 1
    assert "Duplicate" in errors.json()["items"][0]["error"]
