import csv
import io
import os
import random
from locust import HttpUser, task, between

API_KEY = os.environ.get("API_KEY", "your-api-key")
ACCOUNT_IDS = [f"ACC-{i:04d}" for i in range(1, 101)]
CURRENCIES = ["USD", "EUR", "GBP"]

HEADERS = {"X-API-Key": API_KEY}


def _make_csv(rows: int = 50) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["transaction_id", "account_id", "type",
                     "amount", "currency", "timestamp"])
    for i in range(rows):
        writer.writerow([
            f"TXN-LOAD-{random.randint(1, 9_999_999):07d}",
            random.choice(ACCOUNT_IDS),
            random.choice(["CREDIT", "DEBIT"]),
            f"{random.uniform(1, 5000):.2f}",
            random.choice(CURRENCIES),
            "2026-06-01T12:00:00Z",
        ])
    return buf.getvalue().encode()


class TransactionUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(4)
    def list_transactions(self):
        acct = random.choice(ACCOUNT_IDS)
        self.client.get(
            f"/api/v1/transactions?account_id={acct}&page=1&limit=50",
            headers=HEADERS,
            name="/api/v1/transactions",
        )

    @task(3)
    def account_summary(self):
        acct = random.choice(ACCOUNT_IDS)
        self.client.get(
            f"/api/v1/accounts/{acct}/summary",
            headers=HEADERS,
            name="/api/v1/accounts/{id}/summary",
        )

    @task(2)
    def import_small_file(self):
        self.client.post(
            "/api/v1/imports",
            headers=HEADERS,
            files={"file": ("load.csv", _make_csv(50), "text/csv")},
            name="/api/v1/imports",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health/ready", name="/health/ready")