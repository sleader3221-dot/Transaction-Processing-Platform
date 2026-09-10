import csv
import os
import aiofiles
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import verify_api_key
from app.core.id_gen import generate_id
from app.core.validation import validate_csv_header
from app.db.database import get_db
from app.models.import_error import ImportRow
from app.models.import_model import Import, ImportStatus
from app.redis_client.client import get_redis
from app.redis_client.queue import ImportQueue
from app.schemas.import_schema import (
    ImportResponse, ImportStatusResponse,
    ImportErrorsResponse, ImportErrorItem,
)

router = APIRouter()
logger = structlog.get_logger()
settings = get_settings()


@router.post("/imports", response_model=ImportResponse, status_code=202,
             summary="Upload CSV file for async processing")
async def create_import(
    file: UploadFile = File(..., description="CSV file with transactions"),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    client_id: str = Depends(verify_api_key),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    import_id = generate_id()
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{import_id}.csv")

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    written = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(65_536):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit",
                    )
                await out.write(chunk)
    except HTTPException:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    if written == 0:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            validate_csv_header(reader.fieldnames or [])
    except ValueError as exc:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(exc))

    imp = Import(
        id=import_id,
        filename=file.filename,
        file_path=file_path,
        status=ImportStatus.QUEUED,
        client_id=client_id,
    )
    db.add(imp)
    await db.commit()

    queue = ImportQueue(redis)
    await queue.ensure_group()
    await queue.enqueue(import_id)

    logger.info("import_queued", import_id=import_id,
                filename=file.filename, client_id=client_id)

    return ImportResponse(import_id=import_id, status="QUEUED")


@router.get("/imports/{import_id}", response_model=ImportStatusResponse,
            summary="Get import processing status")
async def get_import_status(
    import_id: str,
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    result = await db.execute(select(Import).where(Import.id == import_id))
    imp = result.scalar_one_or_none()
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")

    return ImportStatusResponse(
        import_id=imp.id,
        status=imp.status.value,
        total_rows=imp.total_rows,
        processed_rows=imp.processed_rows,
        successful_rows=imp.successful_rows,
        failed_rows=imp.failed_rows,
        started_at=imp.started_at,
        completed_at=imp.completed_at,
        error_message=imp.error_message,
    )


@router.get("/imports/{import_id}/errors", response_model=ImportErrorsResponse,
            summary="Get paginated import errors")
async def get_import_errors(
    import_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    client_id: str = Depends(verify_api_key),
):
    exists = await db.execute(
        select(Import.id).where(Import.id == import_id)
    )
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Import not found")

    total = (await db.execute(
        select(func.count(ImportRow.id)).where(ImportRow.import_id == import_id)
    )).scalar_one()

    rows = (await db.execute(
        select(ImportRow)
        .where(ImportRow.import_id == import_id)
        .order_by(ImportRow.row_number)
        .offset((page - 1) * limit)
        .limit(limit)
    )).scalars().all()

    return ImportErrorsResponse(
        items=[ImportErrorItem(row=r.row_number,
                               transaction_id=r.transaction_id,
                               error=r.error) for r in rows],
        page=page, limit=limit, total=total,
    )
