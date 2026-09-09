# Transaction Processing Platform

## Quick Start (Local)

```bash
git clone https://github.com/your-username/transaction-platform
cd transaction-platform
cp .env.example .env    # fill in values

docker compose up --build
```

## Create API Key

```bash
docker compose exec api python -m scripts.create_api_key my-client
```

## Run Migrations

```bash
docker compose run --rm migrate
# or directly:
alembic upgrade head
```

## Run Tests

```bash
# Unit tests (no external services)
pytest tests/unit -v

# API tests (requires PostgreSQL; Redis is faked by the test fixtures)
pytest tests/api -v

# Integration tests (requires PostgreSQL, Redis, and the worker)
pytest tests/integration -v

# Concurrency test (requires PostgreSQL)
pytest tests/concurrency -v

# Failure/recovery test (requires PostgreSQL, Redis, and the worker)
pytest tests/failure -v

# All
pytest -v
```

## Generate Test CSV

```bash
python scripts/generate_test_csv.py 500000 big.csv
```

## Performance Test

```bash
pip install locust
locust -f load_test/locustfile.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 5 \
  --run-time 60s --headless \
  -e API_KEY=your-api-key
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/imports | Upload CSV |
| GET | /api/v1/imports/{id} | Import status |
| GET | /api/v1/imports/{id}/errors | Import errors |
| GET | /api/v1/transactions | List transactions |
| GET | /api/v1/transactions/{id} | Single transaction |
| GET | /api/v1/accounts/{id}/summary | Account summary |
| GET | /health/live | Liveness |
| GET | /health/ready | Readiness |

## Redis Design

| Purpose | Key Pattern | TTL |
|---------|-------------|-----|
| Account summary cache | `account:summary:{account_id}` | 300 s |
| Rate limiter | `rate_limit:{client_id}` | 60 s |
| Job queue | `imports:queue` (Stream) | No TTL |
| Dead letter | `imports:dead_letter` (Stream) | No TTL |

**Invalidation:** Cache key is deleted on each batch flush (when new transactions
are inserted for an account) and again when import completes.

**Redis down:** Cache get/set failures are logged as warnings; the app falls
back to PostgreSQL. Rate limiter failures fail open (request is allowed).

## Design Decisions

1. **Redis Streams over Celery/RQ** — consumer groups give exact-once delivery
   semantics; unacknowledged messages survive worker restarts without any DB
   polling.
2. **INSERT ... ON CONFLICT DO NOTHING** — re-processing the same file any number
   of times is safe; the DB constraint is the final deduplication gate.
3. **Streaming CSV** — file is opened with `csv.DictReader`; only one batch
   (<= 1000 rows) is in memory at a time, supporting 500k-row files.
4. **Numeric(20,8)** — financial amounts stored with 8 decimal places to avoid
   floating-point rounding errors.
5. **Sliding-window rate limiter** — Redis sorted set; accurate across multiple
   API replicas unlike a fixed-window counter.

## Known Limitations

- File storage is local (`/app/uploads`). A production system would use
  Azure Blob Storage or S3 with a presigned upload URL.
- No retry back-off for failed imports (dead-lettered immediately after one
  failure).
- Worker uses a single consumer per pod; scaling to multiple workers requires
  each pod to have a unique `CONSUMER_NAME` (already done via hostname).