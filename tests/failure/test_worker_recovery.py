"""
Failure/recovery tests.
Simulate a worker crash by leaving an import in PROCESSING state,
then call _process_import(recovery=True) and verify it completes.
"""
import io
import uuid
import pytest
from sqlalchemy import update, select
from decimal import Decimal
from datetime import datetime, timezone

from app.workers.import_worker import _process_import
from app.models.import_model import Import, ImportStatus
from app.models.transaction import Transaction

VALID_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-REC-1,ACC-REC-1,CREDIT,1000.00,USD,2026-09-01T10:00:00Z
TXN-REC-2,ACC-REC-1,DEBIT,200.00,USD,2026-09-01T10:01:00Z
TXN-REC-3,ACC-REC-1,CREDIT,300.00,USD,2026-09-01T10:02:00Z
"""


@pytest.mark.asyncio
async def test_worker_crash_and_recovery(client, api_key, db_session):
    """
    Flow:
    1. Upload CSV → import is QUEUED
    2. Partially process: set status to PROCESSING (simulates crash mid-way)
    3. Call _process_import(recovery=True) → simulates worker restart
    4. Verify import COMPLETED with correct counts
    5. Verify transactions not duplicated (recovery is idempotent)
    """
    # Step 1: Upload
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("recovery.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    assert upload.status_code == 202
    import_id = upload.json()["import_id"]

    # Step 2: Simulate crash — manually set to PROCESSING
    await db_session.execute(
        update(Import).where(Import.id == import_id).values(
            status=ImportStatus.PROCESSING,
            started_at=datetime.now(timezone.utc),
            processed_rows=1,    # partially processed
            successful_rows=1,
            failed_rows=0,
        )
    )
    await db_session.commit()

    # Verify it's stuck at PROCESSING
    stuck = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    assert stuck.json()["status"] == "PROCESSING"

    # Step 3: Simulate worker restart — recovery=True clears errors, reprocesses
    await _process_import(import_id, recovery=True)

    # Step 4: Verify COMPLETED
    final = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    assert final.status_code == 200
    data = final.json()
    assert data["status"] == "COMPLETED"
    assert data["successful_rows"] == 3
    assert data["failed_rows"] == 0

    # Step 5: Verify transactions not duplicated (run recovery again = idempotent)
    await _process_import(import_id, recovery=True)

    txns = await client.get(
        "/api/v1/transactions?account_id=ACC-REC-1",
        headers={"X-API-Key": api_key},
    )
    assert txns.json()["total"] == 3       # still 3, not 6


@pytest.mark.asyncio
async def test_empty_csv_rejected(client, api_key):
    """Empty CSV should be rejected at upload time."""
    r = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_csv_wrong_extension_rejected(client, api_key):
    """Non-CSV files rejected immediately."""
    r = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("data.xlsx", io.BytesIO(b"fake"), "text/csv")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_csv_missing_columns_rejected(client, api_key):
    """CSV with missing required columns rejected at upload."""
    bad = b"transaction_id,account_id\nT1,A1\n"
    r = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("bad_header.csv", io.BytesIO(bad), "text/csv")},
    )
    assert r.status_code == 400
