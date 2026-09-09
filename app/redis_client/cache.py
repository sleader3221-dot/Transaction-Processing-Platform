import json
from typing import Any, Optional
import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()


class CacheService:
    KEY_PREFIX_ACCOUNT_SUMMARY = "account:summary"

    def __init__(self, redis: aioredis.Redis, ttl: int = 300):
        self.redis = redis
        self.ttl = ttl

    @staticmethod
    def account_key(account_id: str) -> str:
        return f"{CacheService.KEY_PREFIX_ACCOUNT_SUMMARY}:{account_id}"

    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception as exc:
            logger.warning("cache_get_error", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        try:
            await self.redis.setex(key, ttl or self.ttl, json.dumps(value))
        except Exception as exc:
            logger.warning("cache_set_error", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            await self.redis.delete(key)
        except Exception as exc:
            logger.warning("cache_delete_error", key=key, error=str(exc))