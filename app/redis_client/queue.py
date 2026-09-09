import structlog
import redis.asyncio as aioredis

logger = structlog.get_logger()

STREAM = "imports:queue"
GROUP = "workers"
DEAD_LETTER = "imports:dead_letter"


class ImportQueue:
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(self, import_id: str) -> str:
        msg_id = await self.redis.xadd(STREAM, {"import_id": import_id})
        logger.info("import_enqueued", import_id=import_id, msg_id=msg_id)
        return msg_id

    async def read_pending(self, consumer: str, count: int = 10):
        return await self.redis.xreadgroup(
            GROUP, consumer,
            {STREAM: "0"},
            count=count,
        )

    async def read_new(self, consumer: str, count: int = 1, block_ms: int = 2000):
        return await self.redis.xreadgroup(
            GROUP, consumer,
            {STREAM: ">"},
            count=count,
            block=block_ms,
        )

    async def ack(self, msg_id: str) -> None:
        await self.redis.xack(STREAM, GROUP, msg_id)

    async def dead_letter(self, import_id: str, msg_id: str, error: str) -> None:
        await self.redis.xadd(
            DEAD_LETTER,
            {"import_id": import_id, "orig_msg_id": msg_id, "error": error[:500]},
        )
        await self.ack(msg_id)