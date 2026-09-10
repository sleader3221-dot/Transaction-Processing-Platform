"""
Integration tests — call worker directly (no live worker process needed).
These tests use the real DB session; Redis is faked via conftest.
"""
import io
import uuid
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timezone

from app.workers.import_worker import _process_import
from app.models.import_model import ImportStatus
from sqlalchemy import select
from app.models.import_model import Import

VALID_CSV = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-INT-1,ACC-INT-1,CREDIT,1500.00,USD,2026-09-01T10:00:00Z
TXN-INT-2,ACC-INT-1,DEBIT,250.00,USD,2026-09-01T10:01:00Z
TXN-INT-3,ACC-INT-2,CREDIT,700.00,USD,2026-09-01T10:02:00Z
"""


@pytest.mark.asyncio
async def test_full_import_flow(client, api_key):
    """Upload → worker processes → transactions appear in DB."""
    # Upload
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("test.csv", io.BytesIO(VALID_CSV), "text/csv")},
    )
    assert upload.status_code == 202
    import_id = upload.json()["import_id"]

    # Process directly (simulates worker)
    await _process_import(import_id)

    # Verify status
    status = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "COMPLETED"
    assert data["successful_rows"] == 3
    assert data["failed_rows"] == 0
    assert data["total_rows"] == 3

    # Verify transactions in DB
    tx_list = await client.get(
        "/api/v1/transactions?account_id=ACC-INT-1",
        headers={"X-API-Key": api_key},
    )
    assert tx_list.status_code == 200
    assert tx_list.json()["total"] == 2

    # Verify account summary
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
async def test_import_with_validation_errors(client, api_key):
    """Rows with bad data are recorded as errors; good rows are inserted."""
    bad_csv = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-BAD-1,ACC-BAD,CREDIT,100.00,USD,2026-09-01T10:00:00Z
TXN-BAD-2,,DEBIT,50.00,USD,2026-09-01T10:01:00Z
TXN-BAD-3,ACC-BAD,INVALID,100.00,USD,2026-09-01T10:02:00Z
TXN-BAD-4,ACC-BAD,CREDIT,-5.00,USD,2026-09-01T10:03:00Z
"""
    upload = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")},
    )
    import_id = upload.json()["import_id"]

    await _process_import(import_id)

    status = await client.get(
        f"/api/v1/imports/{import_id}",
        headers={"X-API-Key": api_key},
    )
    data = status.json()
    assert data["status"] == "COMPLETED"
    assert data["successful_rows"] == 1   # TXN-BAD-1 only
    assert data["failed_rows"] == 3       # rows 2, 3, 4

    errors = await client.get(
        f"/api/v1/imports/{import_id}/errors?page=1&limit=50",
        headers={"X-API-Key": api_key},
    )
    assert errors.status_code == 200
    assert errors.json()["total"] == 3


@pytest.mark.asyncio
async def test_duplicate_transactions_across_files(client, api_key):
    """Same transaction_id in two imports: stored only once."""
    csv1 = b"""transaction_id,account_id,type,amount,currency,timestamp
TXN-XDUP-1,ACC-XDUP,CREDIT,500.00,USD,2026-09-01T10:00:00Z
"""
    # First import
    up1 = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("dup1.csv", io.BytesIO(csv1), "text/csv")},
    )
    id1 = up1.json()["import_id"]
    await _process_import(id1)

    # Second import (same transaction)
    up2 = await client.post(
        "/api/v1/imports",
        headers={"X-API-Key": api_key},
        files={"file": ("dup2.csv", io.BytesIO(csv1), "text/csv")},
    )
    id2 = up2.json()["import_id"]
    await _process_import(id2)

    # Only one transaction in DB
    txns = await client.get(
        "/api/v1/transactions?account_id=ACC-XDUP",
        headers={"X-API-Key": api_key},
    )
    assert txns.json()["total"] == 1       # DB uniqueness guarantee
