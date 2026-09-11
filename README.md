# Transaction Processing Platform

A production-oriented asynchronous transaction ingestion service built with FastAPI, PostgreSQL, Redis, Docker, and Azure Container Apps.

The platform accepts CSV transaction files, validates rows in a background worker, stores valid transactions, records row-level errors, prevents duplicates at the database boundary, and exposes query and account-summary APIs.

## At A Glance

| Area | Implementation |
| --- | --- |
| API | FastAPI with OpenAPI and API-key authentication |
| Persistence | PostgreSQL with Alembic migrations and indexed queries |
| Queue | Redis Streams with consumer groups and pending-entry recovery |
| Cache | Redis cache-aside account summaries with TTL and invalidation |
| Rate limiting | Redis sorted-set sliding window, 100 requests per 60 seconds by default |
| Worker | Separate Python process/container with streaming CSV processing |
| Local runtime | Docker Compose: API, worker, PostgreSQL, Redis, migrations |
| Cloud runtime | Azure Container Apps plus Azure Container Registry, Neon, and Upstash |

## Public Deployment

The verified API deployment is:

- API: https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io
- Swagger UI: https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io/docs
- Liveness: https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io/health/live
- Readiness: https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io/health/ready

The worker is intentionally private and has no public HTTP URL.

## Repository Layout

```text
app/
  api/              FastAPI routers and endpoint handlers
  core/             Authentication, IDs, validation, logging
  db/               SQLAlchemy base, engine, and sessions
  models/           PostgreSQL persistence models
  redis_client/     Redis client, cache, queue, and limiter
  schemas/          Pydantic request and response schemas
  workers/          Redis Stream consumer and CSV processor
migrations/         Alembic configuration and schema revisions
scripts/            API-key and test-data utilities
tests/              Unit, API, integration, concurrency, and failure tests
load_test/          Locust configuration and reproducible load-test runner
  deploy-fixed-final.ps1  Canonical Azure deployment script
Dockerfile          API/migration image
Dockerfile.worker   Dedicated worker image
docker-compose.yml  Local PostgreSQL, Redis, API, worker, and migration services
ARCHITECTURE.md     System design and technical decisions
```

## Local Quick Start

### Prerequisites

- Docker Desktop with Compose
- Python 3.11 or newer for host-side tests and utilities
- Git

### Start The Stack

```bash
git clone https://github.com/sleader3221-dot/Transaction-Processing-Platform.git
cd Transaction-Processing-Platform
cp .env.example .env
docker compose up --build
```

PowerShell uses `Copy-Item .env.example .env` instead of `cp`.

The migration service runs automatically before the API and worker. Verify services with:

```bash
docker compose ps
curl http://localhost:8000/
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Expected readiness response:

```json
{"status":"ready","postgresql":"ok","redis":"ok"}
```

### Create An API Key

```bash
docker compose exec api python -m scripts.create_api_key demo-client
```

The command prints the raw key once. Store it securely; only its SHA-256 hash is persisted.

## Configuration

Copy `.env.example` to `.env`. Never commit `.env` or real credentials.

| Variable | Purpose | Example |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://txn:txn_secret@postgres:5432/transactions` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `BLOB_CONNECTION_STRING` | Optional shared upload storage URL | Empty locally; Azure Blob in cloud |
| `BLOB_CONTAINER` | Blob container for uploads | `uploads` |
| `APP_ENV` | Runtime environment | `development` or `production` |
| `LOG_LEVEL` | Structured log level | `INFO` |
| `SECRET_KEY` | Application secret | A generated random value |
| `UPLOAD_DIR` | CSV storage directory | `/app/uploads` |
| `MAX_FILE_SIZE_MB` | Upload limit | `500` |
| `RATE_LIMIT_REQUESTS` | Requests per window | `100` |
| `RATE_LIMIT_WINDOW` | Rate-limit window in seconds | `60` |
| `CACHE_TTL` | Account-summary TTL in seconds | `300` |
| `WORKER_BATCH_SIZE` | Database insert batch size | `1000` |
| `WORKER_PROGRESS_INTERVAL` | Progress update interval | `5000` |

For Neon, use its pooled PostgreSQL URL with `sslmode=require`. The application normalizes `sslmode` and `channel_binding` for asyncpg compatibility.

## End-To-End Import Flow

1. An authenticated client uploads a CSV to `POST /api/v1/imports`.
2. The API streams the upload to local storage or Azure Blob Storage, validates the header, and creates an `imports` row.
3. The API adds the import ID to the Redis Stream and returns `202 Accepted` immediately.
4. The worker consumes the message through the `workers` consumer group.
5. The worker reads the CSV incrementally, validates each row, and inserts batches into PostgreSQL.
6. Invalid rows are written to `import_errors`; valid rows are protected by the unique `transaction_id` constraint.
7. Progress and final status are written to PostgreSQL.
8. Account-summary cache entries are invalidated for affected accounts.
9. The worker acknowledges the stream message only after successful processing.

## CSV Contract

Required header:

```csv
transaction_id,account_id,type,amount,currency,timestamp
TXN-001,ACC-1001,CREDIT,1500.00,USD,2026-09-01T10:00:00Z
TXN-002,ACC-1001,DEBIT,250.00,USD,2026-09-01T10:01:00Z
```

Validation rules:

- `transaction_id` and `account_id` are required and non-empty.
- `type` is `CREDIT` or `DEBIT`.
- `amount` is positive and stored as `NUMERIC(20,8)`.
- `currency` must be a valid ISO 4217 code.
- `timestamp` must be parseable as a timestamp.
- Row errors do not fail the entire import.
- Duplicate rows within one file are recorded as errors.
- Duplicates across files are safely ignored by the database uniqueness constraint.

## API Reference

All business endpoints require `X-API-Key`. Health endpoints do not.

### Import endpoints

```text
POST /api/v1/imports
GET  /api/v1/imports/{import_id}
GET  /api/v1/imports/{import_id}/errors?page=1&limit=50
```

Upload example:

```bash
curl -X POST http://localhost:8000/api/v1/imports \
  -H "X-API-Key: $API_KEY" \
  -F "file=@transactions.csv"
```

### Transaction endpoints

```text
GET /api/v1/transactions/{transaction_id}
GET /api/v1/transactions?account_id=ACC-1001&type=DEBIT&currency=USD&page=1&limit=50
```

Supported list filters include account, type, currency, `date_from`, `date_to`, pagination, and sorting. Sorting is constrained to supported database columns.

### Account summary

```text
GET /api/v1/accounts/{account_id}/summary
```

The response includes credits, debits, transaction count, and balance. PostgreSQL is the source of truth; Redis is an optimization.

### Service endpoints

```text
GET /
GET /health/live
GET /health/ready
GET /docs
GET /openapi.json
```

## Database And Migrations

The schema includes `api_keys`, `imports`, `transactions`, and `import_errors`.

```bash
# Apply migrations inside Compose
docker compose run --rm migrate

# Inspect migration state
docker compose exec api alembic -c migrations/alembic.ini current

# Roll back one revision
docker compose exec api alembic -c migrations/alembic.ini downgrade -1
```

Important database guarantees:

- Unique `transactions.transaction_id` is the final duplicate-prevention boundary.
- Positive amount check constraint rejects invalid persisted values.
- Composite account/time and account/type indexes support common filters.
- Import errors reference their import and cascade on import deletion.

## Redis Responsibilities

| Capability | Redis primitive | Behavior when Redis is unavailable |
| --- | --- | --- |
| Queue | Stream `imports:queue`, group `workers` | Imports cannot be queued and the request fails visibly |
| Recovery | Pending Entry List and dead-letter stream | Unacknowledged jobs remain recoverable |
| Summary cache | `account:summary:{account_id}` JSON string | Query falls back to PostgreSQL |
| Rate limiting | `rate_limit:{client_id}` sorted set | Requests fail open according to the limiter policy |

Summary cache TTL is `CACHE_TTL` seconds. New transaction batches invalidate affected account keys.

## Tests

Start PostgreSQL and Redis with Compose, then run tests from the repository root. On PowerShell:

```powershell
$env:DATABASE_URL="postgresql://txn:txn_secret@localhost:5432/transactions"
$env:REDIS_URL="redis://localhost:6379/0"
python -m pytest -q
```

Test groups:

```bash
python -m pytest tests/unit -v
python -m pytest tests/api -v
python -m pytest tests/integration -v
python -m pytest tests/concurrency -v
python -m pytest tests/failure -v
```

The verified repository state passes 39 tests. The suite covers validation, uploads, status and error APIs, query filtering, summaries, duplicate concurrency, and worker recovery.

## Performance Testing

Performance testing is reproducible but benchmark numbers must be recorded from the environment being evaluated; this repository does not claim unmeasured results.

```bash
python load_test/run_performance_tests.py
```

Record at minimum:

- environment and resource sizes
- dataset row counts
- concurrent users and duration
- requests per second
- average, p50, p95, and p99 latency
- error rate and rate-limit responses
- import processing duration
- API, worker, PostgreSQL, and Redis resource usage

See [PERFORMANCE_TESTING_COMPLETE.md](PERFORMANCE_TESTING_COMPLETE.md) for the runbook.

## Azure Deployment

The canonical Windows deployment command is:

```powershell
$env:DATABASE_URL="postgresql://..."
$env:REDIS_URL="rediss://..."
.\deploy-fixed-final.ps1
```

The script:

- reuses an authenticated Azure CLI session
- uses the subscription-approved region
- builds separate API and worker images
- tags images immutably
- stores runtime values as Container Apps secrets
- deploys the API with external ingress on port 8000
- deploys the worker with no HTTP ingress
- validates provisioning and running state

See [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) for prerequisites, architecture, and troubleshooting.

## Security And Operational Notes

- `.env` is ignored and must never be committed.
- API keys are hashed before persistence.
- Secrets are passed through Azure Container Apps secret references.
- Logs include useful IDs but must not contain credentials or raw API keys.
- The current upload volume is shared local/container storage; production scale-out should use Azure Blob Storage.
- Rotate any credential that has been exposed during development or support work.

## Known Limitations

- A technical walkthrough video is an external submission artifact and is not stored in this repository.
- Performance result files must be generated in the target environment rather than copied from estimates.
- Local file storage should be replaced with durable object storage for multi-replica production uploads.
- Redis queue depth autoscaling and centralized observability are future production enhancements.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md)
- [PERFORMANCE_TESTING_COMPLETE.md](PERFORMANCE_TESTING_COMPLETE.md)
- [PERFORMANCE_RESULTS.md](load_test/PERFORMANCE_RESULTS.md) — measured local smoke run
- [`.env.example`](.env.example)

## License

MIT
