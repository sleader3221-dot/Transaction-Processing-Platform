import time
import redis.asyncio as aioredis


class SlidingWindowRateLimiter:
    def __init__(self, redis: aioredis.Redis, limit: int = 100, window: int = 60):
        self.redis = redis
        self.limit = limit
        self.window = window

    async def is_allowed(self, client_id: str) -> tuple[bool, int]:
        key = f"rate_limit:{client_id}"
        now = time.time()
        window_start = now - self.window

        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window + 1)
            results = await pipe.execute()

        count: int = results[2]
        return count <= self.limit, count