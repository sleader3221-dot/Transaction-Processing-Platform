import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.config import get_settings
from app.db.database import get_db
from app.models.transaction import Transaction
from app.redis_client.client import get_redis
from app.redis_client.cache import CacheService
from app.schemas.account_schema import AccountSummaryResponse

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


@router.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponse,
            summary="Account summary (credits, debits, balance)")
async def get_account_summary(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    client_id: str = Depends(verify_api_key),
):
    cache = CacheService(redis, ttl=settings.CACHE_TTL)
    cache_key = CacheService.account_key(account_id)

    cached = await cache.get(cache_key)
    if cached:
        logger.debug("account_summary_cache_hit", account_id=account_id)
        return AccountSummaryResponse(**cached)

    row = (await db.execute(
        select(
            func.sum(
                case((Transaction.type == "CREDIT", Transaction.amount), else_=0)
            ).label("total_credits"),
            func.sum(
                case((Transaction.type == "DEBIT", Transaction.amount), else_=0)
            ).label("total_debits"),
            func.count(Transaction.id).label("transaction_count"),
        ).where(Transaction.account_id == account_id)
    )).fetchone()

    if not row or row.transaction_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    credits = float(row.total_credits or 0)
    debits = float(row.total_debits or 0)

    summary = AccountSummaryResponse(
        account_id=account_id,
        total_credits=credits,
        total_debits=debits,
        transaction_count=row.transaction_count,
        balance=credits - debits,
    )

    await cache.set(cache_key, summary.model_dump())
    logger.debug("account_summary_cached", account_id=account_id)

    return summary
