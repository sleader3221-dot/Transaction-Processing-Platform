import pytest
import csv
import io
from app.core.validation import validate_csv_header


def test_valid_header():
    validate_csv_header(["transaction_id", "account_id", "type", "amount", "currency", "timestamp"])


def test_missing_column():
    with pytest.raises(ValueError, match="missing required columns"):
        validate_csv_header(["transaction_id", "account_id", "type"])


def test_case_insensitive_header():
    validate_csv_header(["TRANSACTION_ID", "ACCOUNT_ID", "TYPE", "AMOUNT", "CURRENCY", "TIMESTAMP"])


def test_extra_columns_allowed():
    validate_csv_header(["transaction_id", "account_id", "type", "amount", "currency", "timestamp", "extra"])