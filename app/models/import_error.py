from sqlalchemy import Column, String, Integer, ForeignKey, Index
from app.db.base import Base


class ImportRow(Base):
    __tablename__ = "import_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_id = Column(
        String(26),
        ForeignKey("imports.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number = Column(Integer, nullable=False)
    transaction_id = Column(String(255), nullable=True)
    error = Column(String(2048), nullable=False)

    __table_args__ = (
        Index("ix_import_errors_import_id", "import_id"),
    )
