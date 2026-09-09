import enum
from sqlalchemy import Column, String, Integer, DateTime, Enum, text
from app.db.base import Base


class ImportStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Import(Base):
    __tablename__ = "imports"

    id = Column(String(26), primary_key=True)
    status = Column(
        Enum(ImportStatus, name="import_status"),
        nullable=False,
        default=ImportStatus.QUEUED,
        index=True,
    )
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=True)
    total_rows = Column(Integer, nullable=True)
    processed_rows = Column(Integer, default=0, nullable=False)
    successful_rows = Column(Integer, default=0, nullable=False)
    failed_rows = Column(Integer, default=0, nullable=False)
    error_message = Column(String(2048), nullable=True)
    client_id = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
    )