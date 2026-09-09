import csv
import random
import sys
from datetime import datetime, timedelta, timezone

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"]
TYPES = ["CREDIT", "DEBIT"]


def generate(rows: int, path: str):
    base_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["transaction_id", "account_id", "type",
                         "amount", "currency", "timestamp"])
        for i in range(1, rows + 1):
            ts = base_ts + timedelta(seconds=i)
            writer.writerow([
                f"TXN-{i:010d}",
                f"ACC-{random.randint(1, 1000):04d}",
                random.choice(TYPES),
                f"{random.uniform(0.01, 100_000):.2f}",
                random.choice(CURRENCIES),
                ts.isoformat(),
            ])
    print(f"Generated {rows} rows -> {path}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    path = sys.argv[2] if len(sys.argv) > 2 else "test_data.csv"
    generate(n, path)