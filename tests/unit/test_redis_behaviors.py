import asyncio

import fakeredis.aioredis as fakeredis
import pytest

from app.redis_client.queue import GROUP, STREAM, ImportQueue
from app.redis_client.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_pending_stream_messages_are_reclaimed():
    redis = fakeredis.FakeRedis(decode_responses=True)
    queue = ImportQueue(redis)
    await queue.ensure_group()
    message_id = await queue.enqueue("recovery-import")

    pending = await redis.xreadgroup(
        GROUP, "crashed-worker", {STREAM: ">"}, count=1
    )
    assert pending[0][1][0][0] == message_id

    recovered = await queue.read_pending("replacement-worker", count=10)
    assert recovered[0][1][0][1]["import_id"] == "recovery-import"
    await redis.aclose()


@pytest.mark.asyncio
async def test_rate_limiter_counts_concurrent_events_individually():
    redis = fakeredis.FakeRedis(decode_responses=True)
    limiter = SlidingWindowRateLimiter(redis, limit=2, window=60)

    results = await asyncio.gather(
        limiter.is_allowed("client"),
        limiter.is_allowed("client"),
        limiter.is_allowed("client"),
    )

    assert [allowed for allowed, _ in results].count(True) == 2
    assert [allowed for allowed, _ in results].count(False) == 1
    await redis.aclose()
