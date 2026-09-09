from typing import Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.db.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction_schema import TransactionResponse, TransactionsListResponse

router = APIRouter()
logger = structlog.get_logger()

SORT_COLUMNS = {
    "timestamp": Transaction.timestamp,
    "amount": Transaction.amount,
    "transaction_id": Transaction.transaction_id,
    "created_at": Transaction.created_at,
}


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse,
            summary="Get single transaction by ID")
async def get_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    result = await db.execute(
        select(Transaction).where(Transaction.transaction_id == transaction_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(tx)


@router.get("/transactions", response_model=TransactionsListResponse,
            summary="List transactions with filters and pagination")
async def list_transactions(
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    type: Optional[str] = Query(None, description="CREDIT or DEBIT"),
    currency: Optional[str] = Query(None, description="ISO 4217 currency code"),
    date_from: Optional[datetime] = Query(None, description="Inclusive start timestamp"),
    date_to: Optional[datetime] = Query(None, description="Inclusive end timestamp"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    sort_by: str = Query("timestamp", enum=list(SORT_COLUMNS)),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    filters = []
    if account_id:
        filters.append(Transaction.account_id == account_id)
    if type:
        if type.upper() not in ("CREDIT", "DEBIT"):
            raise HTTPException(status_code=400, detail="type must be CREDIT or DEBIT")
        filters.append(Transaction.type == type.upper())
    if currency:
        filters.append(Transaction.currency == currency.upper())
    if date_from:
        filters.append(Transaction.timestamp >= date_from)
    if date_to:
        filters.append(Transaction.timestamp <= date_to)

    where_clause = and_(*filters) if filters else True

    total = (await db.execute(
        select(func.count(Transaction.id)).where(where_clause)
    )).scalar_one()

    col = SORT_COLUMNS[sort_by]
    order = col.desc() if sort_order == "desc" else col.asc()

    rows = (await db.execute(
        select(Transaction)
        .where(where_clause)
        .order_by(order)
        .offset((page - 1) * limit)
        .limit(limit)
    )).scalars().all()

    return TransactionsListResponse(
        items=[TransactionResponse.model_validate(r) for r in rows],
        page=page, limit=limit, total=total,
    )