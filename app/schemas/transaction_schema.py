from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime
from uuid import UUID


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transaction_id: str
    account_id: str
    type: str
    amount: Decimal
    currency: str
    timestamp: datetime
    import_id: str | None = None
    created_at: datetime


class TransactionsListResponse(BaseModel):
    items: list[TransactionResponse]
    page: int
    limit: int
    total: int
