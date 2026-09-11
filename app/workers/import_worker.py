import asyncio
import csv
import os
import signal
import socket
import tempfile
from datetime import datetime, timezone

import structlog
from sqlalchemy import update, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.core.validation import validate_transaction_row
from app.core import blob_storage
from app.db.database import get_db_session
from app.models.import_error import ImportRow
from app.models.import_model import Import, ImportStatus
from app.models.transaction import Transaction
from app.redis_client.client import get_redis
from app.redis_client.queue import ImportQueue, STREAM, GROUP

settings = get_settings()
logger = structlog.get_logger()
CONSUMER_NAME = f"worker-{socket.gethostname()}"
BATCH_SIZE = settings.WORKER_BATCH_SIZE
PROGRESS_EVERY = settings.WORKER_PROGRESS_INTERVAL

MAX_RETRIES = 3
BASE_BACKOFF = 2  # seconds

_running = True


def _handle_signal(sig, frame):
    global _running
    logger.info("shutdown_signal_received", signal=sig)
    _running = False


async def run_worker():
    redis = await get_redis()
    queue = ImportQueue(redis)
    await queue.ensure_group()
    logger.info("worker_started", consumer=CONSUMER_NAME)

    await _recover_pending(queue)

    while _running:
        try:
            messages = await queue.read_new(CONSUMER_NAME, count=1, block_ms=2000)
        except Exception as exc:
            logger.error("queue_read_error", error=str(exc))
            await asyncio.sleep(2)
            continue

        if not messages:
            continue

        for _stream, entries in messages:
            for msg_id, data in entries:
                import_id = data.get("import_id")
                if import_id:
                    await _handle_import(queue, import_id, msg_id)


async def _recover_pending(queue: ImportQueue):
    try:
        messages = await queue.read_pending(CONSUMER_NAME, count=20)
    except Exception as exc:
        logger.warning("pending_read_error", error=str(exc))
        return

    if not messages:
        return

    for _stream, entries in messages:
        for msg_id, data in entries:
            import_id = data.get("import_id")
            if import_id:
                logger.info("recovering_pending", import_id=import_id, msg_id=msg_id)
                await _handle_import(queue, import_id, msg_id, recovery=True)


async def _handle_import(queue: ImportQueue, import_id: str,
                         msg_id: str, recovery: bool = False):
    """Process import with retry-on-failure and exponential backoff."""
    last_exc = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await _process_import(import_id, recovery=(recovery or attempt > 1))
            await queue.ack(msg_id)
            if attempt > 1:
                logger.info("import_recovered_after_retry",
                            import_id=import_id, attempt=attempt)
            return
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                backoff = BASE_BACKOFF ** attempt
                logger.warning(
                    "import_attempt_failed",
                    import_id=import_id,
                    attempt=attempt,
                    next_retry_in=backoff,
                    error=str(exc),
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "import_permanently_failed",
                    import_id=import_id,
                    attempts=MAX_RETRIES,
                    error=str(exc),
                )

    # All retries exhausted
    async with get_db_session() as db:
        await db.execute(
            update(Import).where(Import.id == import_id).values(
                status=ImportStatus.FAILED,
                error_message=f"Failed after {MAX_RETRIES} attempts: {str(last_exc)[:2000]}",
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
    await queue.dead_letter(import_id, msg_id, str(last_exc))


async def _process_import(import_id: str, recovery: bool = False):
    async with get_db_session() as db:
        row = (await db.execute(
            select(Import).where(Import.id == import_id)
        )).scalar_one_or_none()

        if not row:
            raise ValueError(f"Import {import_id} not found in DB")

        if row.status == ImportStatus.COMPLETED:
            logger.info("import_already_completed", import_id=import_id)
            return

        if recovery:
            await db.execute(
                ImportRow.__table__.delete().where(
                    ImportRow.import_id == import_id
                )
            )

        await db.execute(
            update(Import).where(Import.id == import_id).values(
                status=ImportStatus.PROCESSING,
                started_at=datetime.now(timezone.utc),
                processed_rows=0, successful_rows=0, failed_rows=0,
            )
        )
        await db.commit()
        file_path = row.file_path

    if file_path and file_path.startswith("blob://"):
        temporary_file = tempfile.NamedTemporaryFile(
            prefix=f"{import_id}-", suffix=".csv", delete=False
        )
        temporary_path = temporary_file.name
        temporary_file.close()
        try:
            await asyncio.to_thread(blob_storage.download_file, file_path, temporary_path)
            await _stream_csv(import_id, temporary_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
    else:
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"Upload file missing: {file_path}")
        await _stream_csv(import_id, file_path)


async def _stream_csv(import_id: str, file_path: str):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        total_rows = sum(1 for _ in f) - 1

    async with get_db_session() as db:
        await db.execute(
            update(Import).where(Import.id == import_id)
            .values(total_rows=max(total_rows, 0))
        )
        await db.commit()

    seen_ids: set[str] = set()
    tx_batch: list[dict] = []
    err_batch: list[dict] = []
    processed = successful = failed = 0

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_num, raw in enumerate(reader, start=1):
            processed += 1
            row = {k.strip(): v.strip() for k, v in raw.items()}

            try:
                validated = validate_transaction_row(row)
                tx_id = validated["transaction_id"]

                if tx_id in seen_ids:
                    err_batch.append(_mk_err(import_id, row_num, tx_id,
                                             "Duplicate transaction_id within file"))
                    failed += 1
                else:
                    seen_ids.add(tx_id)
                    tx_batch.append({**validated, "import_id": import_id})
                    successful += 1

            except ValueError as exc:
                err_batch.append(_mk_err(import_id, row_num,
                                         row.get("transaction_id", ""),
                                         str(exc)[:2048]))
                failed += 1

            if len(tx_batch) >= BATCH_SIZE or len(err_batch) >= BATCH_SIZE:
                await _flush(tx_batch, err_batch)
                tx_batch.clear()
                err_batch.clear()

            if processed % PROGRESS_EVERY == 0:
                await _update_progress(import_id, processed, successful, failed)
                logger.info("import_progress", import_id=import_id,
                            processed=processed, total=total_rows)

    if tx_batch or err_batch:
        await _flush(tx_batch, err_batch)

    async with get_db_session() as db:
        await db.execute(
            update(Import).where(Import.id == import_id).values(
                status=ImportStatus.COMPLETED,
                processed_rows=processed,
                successful_rows=successful,
                failed_rows=failed,
                completed_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    await _invalidate_caches(import_id)

    logger.info("import_completed", import_id=import_id,
                processed=processed, successful=successful, failed=failed)


async def _flush(tx_batch: list[dict], err_batch: list[dict]) -> int:
    cross_file_dups = 0

    async with get_db_session() as db:
        if tx_batch:
            stmt = pg_insert(Transaction).values(tx_batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=["transaction_id"])
            result = await db.execute(stmt)
            inserted = result.rowcount
            cross_file_dups = len(tx_batch) - inserted

        if err_batch:
            await db.execute(ImportRow.__table__.insert().values(err_batch))

        await db.commit()

    if tx_batch:
        redis = await get_redis()
        for acct in {t["account_id"] for t in tx_batch}:
            await redis.delete(f"account:summary:{acct}")

    return cross_file_dups


async def _update_progress(import_id: str, processed: int,
                           successful: int, failed: int):
    async with get_db_session() as db:
        await db.execute(
            update(Import).where(Import.id == import_id).values(
                processed_rows=processed,
                successful_rows=successful,
                failed_rows=failed,
            )
        )
        await db.commit()


async def _invalidate_caches(import_id: str):
    async with get_db_session() as db:
        result = await db.execute(
            select(Transaction.account_id)
            .where(Transaction.import_id == import_id)
            .distinct()
        )
        account_ids = [r[0] for r in result.fetchall()]

    redis = await get_redis()
    for acct in account_ids:
        await redis.delete(f"account:summary:{acct}")


def _mk_err(import_id: str, row_num: int,
            tx_id: str, error: str) -> dict:
    return {"import_id": import_id, "row_number": row_num,
            "transaction_id": tx_id, "error": error}


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    asyncio.run(run_worker())
