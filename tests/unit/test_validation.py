import pytest
from decimal import Decimal
from app.core.validation import validate_transaction_row


def valid_row(**overrides):
    base = {
        "transaction_id": "TXN-001",
        "account_id": "ACC-1001",
        "type": "CREDIT",
        "amount": "1500.00",
        "currency": "USD",
        "timestamp": "2026-09-01T10:00:00Z",
    }
    return {**base, **overrides}


def test_valid_row_passes():
    result = validate_transaction_row(valid_row())
    assert result["amount"] == Decimal("1500.00")
    assert result["type"] == "CREDIT"
    assert result["currency"] == "USD"


def test_missing_transaction_id():
    with pytest.raises(ValueError, match="transaction_id"):
        validate_transaction_row(valid_row(transaction_id=""))


def test_missing_account_id():
    with pytest.raises(ValueError, match="account_id"):
        validate_transaction_row(valid_row(account_id=""))


def test_invalid_type():
    with pytest.raises(ValueError, match="type"):
        validate_transaction_row(valid_row(type="TRANSFER"))


def test_zero_amount():
    with pytest.raises(ValueError, match="greater than zero"):
        validate_transaction_row(valid_row(amount="0"))


def test_negative_amount():
    with pytest.raises(ValueError, match="greater than zero"):
        validate_transaction_row(valid_row(amount="-100"))


def test_invalid_amount():
    with pytest.raises(ValueError, match="not a valid number"):
        validate_transaction_row(valid_row(amount="abc"))


def test_invalid_currency():
    with pytest.raises(ValueError, match="currency"):
        validate_transaction_row(valid_row(currency="INVALID"))


def test_invalid_timestamp():
    with pytest.raises(ValueError, match="timestamp"):
        validate_transaction_row(valid_row(timestamp="not-a-date"))


def test_debit_type_valid():
    result = validate_transaction_row(valid_row(type="DEBIT"))
    assert result["type"] == "DEBIT"


def test_case_insensitive_type():
    result = validate_transaction_row(valid_row(type="credit"))
    assert result["type"] == "CREDIT"