from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ImportResponse(BaseModel):
    import_id: str
    status: str


class ImportStatusResponse(BaseModel):
    import_id: str
    status: str
    total_rows: Optional[int]
    processed_rows: int
    successful_rows: int
    failed_rows: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str] = None


class ImportErrorItem(BaseModel):
    row: int
    transaction_id: Optional[str]
    error: str


class ImportErrorsResponse(BaseModel):
    items: list[ImportErrorItem]
    page: int
    limit: int
    total: int