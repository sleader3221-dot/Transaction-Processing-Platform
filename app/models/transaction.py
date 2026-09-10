import uuid
import enum
from sqlalchemy import Column, String, Numeric, DateTime, Enum, Index, text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class TransactionType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String(255), nullable=False, unique=True)
    account_id = Column(String(255), nullable=False)
    type = Column(Enum(TransactionType, name="transaction_type"), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(3), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    import_id = Column(String(26), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"))

    __table_args__ = (
        Index("ix_txn_account_timestamp", "account_id", "timestamp"),
        Index("ix_txn_account_type", "account_id", "type"),
        Index("ix_txn_currency", "currency"),
        Index("ix_txn_timestamp", "timestamp"),
        Index("ix_txn_import_id", "import_id"),
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
    )
