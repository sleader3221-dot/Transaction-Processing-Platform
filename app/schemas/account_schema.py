from pydantic import BaseModel


class AccountSummaryResponse(BaseModel):
    account_id: str
    total_credits: float
    total_debits: float
    transaction_count: int
    balance: float
