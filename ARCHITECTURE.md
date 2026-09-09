# ARCHITECTURE.md

## 1. System Architecture

```
Internet
   |
   v
+-----------------------------+
|       FastAPI (API)         |<- X-API-Key auth
|  /api/v1/imports            |<- Rate limit (Redis sliding-window)
|  /api/v1/transactions       |
|  /api/v1/accounts/{id}/sum  |<- Cache-aside (Redis)
|  /health/live /health/ready |
+--------------+--------------+
               |
      +--------+--------+
      v                 v
+--------------+  +----------------------+
| PostgreSQL   |  | Redis                |
|              |  | +------------------+ |
| api_keys     |  | | Streams queue    | |
| imports      |  | | Account cache    | |
| transactions |  | | Rate limiter     | |
| import_errors|  | +------------------+ |
+--------------+  +----------+-----------+
                            |
                            v
                   +-------------------+
                   | Worker Process    |
                   | (separate pod)    |
                   | Streams XREAD     |
                   | CSV streaming     |
                   | Bulk INSERT       |
                   +-------------------+
```

## 2. Database Schema

### Tables

| Table | Purpose | Key Constraints |
|-------|---------|-----------------|
| api_keys | Client authentication | UNIQUE(client_id) |
| imports | File import lifecycle | status INDEX |
| transactions | Validated transactions | UNIQUE(transaction_id) |
| import_errors | Per-row validation failures | FK -> imports |

### Important Indexes

| Index | Columns | Reason |
|-------|---------|--------|
| uq_transactions_txn_id | transaction_id | Duplicate prevention (primary) |
| ix_txn_account_timestamp | account_id, timestamp | Date-range queries per account |
| ix_txn_account_type | account_id, type | Filter by type per account |
| ix_txn_currency | currency | Currency filter |
| ix_imports_status | status | Worker polling |

## 3. Import Processing Flow

QUEUED -> PROCESSING -> COMPLETED / FAILED

1. Client POSTs CSV -> API saves file, creates Import record, enqueues to Redis Stream.
2. Worker picks up message via XREADGROUP with consumer group.
3. Worker streams CSV, validates rows, bulk-inserts in 1000-row batches.
4. Per-batch: invalidate account summary cache.
5. On completion: update Import status, invalidate remaining caches.
6. Worker ACKs the stream message.

## 4. Redis Usage

| Feature | Mechanism | Key |
|---------|-----------|-----|
| Job queue | Redis Stream + consumer group | `imports:queue` |
| Dead letter | Redis Stream | `imports:dead_letter` |
| Account cache | String (JSON) | `account:summary:{id}` |
| Rate limiting | Sorted Set (sliding window) | `rate_limit:{client_id}` |

## 5. Worker Architecture

- Separate process/container
- Consumer group `workers`; each worker has unique name (hostname-based)
- On startup: reads PEL (pending) first -> crash recovery
- Batch size: 1000 rows; progress update every 5000 rows

## 6. Failure / Recovery Strategy

Worker crash during processing:
1. Redis Stream retains message in PEL (pending entry list).
2. On worker restart, `XREADGROUP ... ID=0` returns pending messages.
3. Worker checks DB: if status = PROCESSING -> clear errors, reset to QUEUED, reprocess.
4. `INSERT ... ON CONFLICT DO NOTHING` makes reprocessing idempotent.

## 7. Caching Strategy

- **Pattern:** Cache-aside (read-through, write-invalidate)
- **TTL:** 300 seconds
- **Invalidation:** delete key whenever new transactions for an account are inserted
- **Failure:** Redis down -> silent fallback to DB (logged as WARNING)
- **Source of truth:** PostgreSQL always

## 8. Azure Architecture

- Azure Container Apps (API + Worker as separate apps)
- Azure Container Registry (private image repository)
- Neon (PostgreSQL, free tier)
- Upstash (Redis, free tier)
- Secrets managed via Container Apps environment variables (not committed to repo)

## 9. Technical Decisions & Trade-offs

| # | Decision | Trade-off |
|---|----------|-----------|
| 1 | Redis Streams | More complex than Lists; consumer groups add setup but give delivery guarantees |
| 2 | asyncpg | Faster than psycopg2 for async workloads; requires async everywhere |
| 3 | Local file storage | Simple for 72h; production needs blob storage for multi-instance API |
| 4 | ON CONFLICT DO NOTHING | Silently ignores cross-file duplicates; counted as "successful" not "failed" |
| 5 | In-memory seen_ids set | Fast O(1) lookup; ~50 MB for 500k rows; would use Redis Set for multi-worker |