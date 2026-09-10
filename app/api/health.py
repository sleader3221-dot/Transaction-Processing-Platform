from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.redis_client.client import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health/live")
async def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db), redis=Depends(get_redis)):
    errors = {}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        errors["postgresql"] = str(exc)

    try:
        await redis.ping()
    except Exception as exc:
        errors["redis"] = str(exc)

    if errors:
        from fastapi import HTTPException
        raise HTTPException(status_code=503,
                            detail={"status": "not_ready", "errors": errors})

    return {"status": "ready", "postgresql": "ok", "redis": "ok"}
