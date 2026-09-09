import csv
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any

import pycountry

VALID_CURRENCIES = {c.alpha_3 for c in pycountry.currencies}

REQUIRED_COLUMNS = {"transaction_id", "account_id", "type", "amount", "currency", "timestamp"}


def validate_csv_header(fieldnames: list[str]) -> None:
    present = {f.strip().lower() for f in (fieldnames or [])}
    required = {c.lower() for c in REQUIRED_COLUMNS}
    missing = required - present
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")


def validate_transaction_row(row: dict[str, Any]) -> dict:
    errors: list[str] = []

    tx_id = str(row.get("transaction_id", "")).strip()
    if not tx_id:
        errors.append("transaction_id is required and must not be empty")

    account_id = str(row.get("account_id", "")).strip()
    if not account_id:
        errors.append("account_id is required and must not be empty")

    tx_type = str(row.get("type", "")).strip().upper()
    if tx_type not in ("CREDIT", "DEBIT"):
        errors.append(f"type must be CREDIT or DEBIT, got '{row.get('type')}'")

    amount = None
    raw_amount = str(row.get("amount", "")).strip()
    try:
        amount = Decimal(raw_amount)
        if amount <= 0:
            errors.append("amount must be greater than zero")
    except InvalidOperation:
        errors.append(f"amount is not a valid number: '{raw_amount}'")

    currency = str(row.get("currency", "")).strip().upper()
    if currency not in VALID_CURRENCIES:
        errors.append(f"currency '{currency}' is not a valid ISO 4217 code")

    ts = None
    raw_ts = str(row.get("timestamp", "")).strip()
    try:
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        errors.append(f"timestamp is not a valid ISO 8601 datetime: '{raw_ts}'")

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "transaction_id": tx_id,
        "account_id": account_id,
        "type": tx_type,
        "amount": amount,
        "currency": currency,
        "timestamp": ts,
    }