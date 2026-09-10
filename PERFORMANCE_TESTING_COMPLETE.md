# Performance Testing Runbook

This document defines a reproducible performance test. It intentionally does not present estimated numbers as measured results. Run the test in the target environment and record the generated metrics before submission.

## Scope

The test should cover:

- concurrent authenticated API requests
- transaction listing and filtering
- account-summary cache hits and misses
- import submission and asynchronous processing
- large CSV processing
- error rate and rate-limit behavior

## Environment Record

Before running, record:

```text
Date:
Git commit:
Environment: local Docker / Azure Container Apps
API URL:
API replicas:
Worker replicas:
PostgreSQL plan and region:
Redis plan and region:
CPU and memory limits:

Dataset sizes:
Concurrent users:
Spawn rate:
Duration:
```

## Local Preparation

```bash
docker compose down
docker compose up -d --build
docker compose ps
```

Create a client key and test data:

```bash
docker compose exec api python -m scripts.create_api_key perf-client
docker compose exec api python scripts/generate_test_csv.py 10000 /app/uploads/test_10k.csv
docker compose exec api python scripts/generate_test_csv.py 100000 /app/uploads/test_100k.csv
```

The API and worker share the `uploads` volume in Compose.

## Load Test

The Locust scenario is in `load_test/locustfile.py`. Run a headless test after setting the API key expected by the scenario:

```bash
$env:API_KEY="<key printed by create_api_key>"
locust -f load_test/locustfile.py \
  --host http://localhost:8000 \
  --users 50 \
  --spawn-rate 10 \
  --run-time 60s \
  --headless \
  --csv=load_test/results
```

On PowerShell, use backticks for line continuation or run the command on one line. The CSV outputs should remain uncommitted unless they are explicitly selected as final evidence.

The repository also includes:

```bash
python load_test/run_performance_tests.py
```

Review that script before running it against a new environment and supply credentials through environment variables rather than source files.

## Metrics To Capture

| Metric | Source |
| --- | --- |
| Requests per second | Locust statistics |
| Average latency | Locust statistics |
| p50, p95, p99 latency | Locust statistics |
| Error rate | Locust errors and response counts |
| 429 rate | API response classification |
| Import duration | First upload to `COMPLETED` status |
| Processed/successful/failed rows | Import status endpoint |
| CPU and memory | Docker stats or Azure metrics |
| Queue depth | Redis Stream pending and stream length |

## Recommended Scenarios

### API concurrency

50 users for 60 seconds against transaction listing, account summaries, health, and small import submissions.

### Cache comparison

1. Query a cold account summary and record latency.
2. Repeat the same query and record the cache-hit latency.
3. Insert/import a transaction for the account.
4. Confirm the next summary reflects PostgreSQL and the cache was invalidated.

### Large import

Run 10K, 100K, and, where resources allow, 500K-row CSVs. Record processing time, row counts, memory peak, and worker logs. Do not claim a result until the run completes in the target environment.

### Failure recovery

1. Submit an import.
2. Stop the worker while the import is processing.
3. Start the worker again.
4. Confirm the pending Redis Stream entry is recovered and the import reaches a terminal state.
5. Confirm database uniqueness prevents duplicate transaction records.

## Results Template

Copy this section into a dated results file after running:

```text
Commit:
Environment:
Dataset:
Users / spawn rate / duration:

Requests/sec:
Average latency:
p50:
p95:
p99:
Error rate:
429 responses:

Import duration:
Rows processed:
Rows successful:
Rows rejected:
Peak API memory:
Peak worker memory:
Database observations:
Redis observations:

Bottlenecks:
Actions taken:
Limitations:
```

## Interpretation

Compare runs rather than relying on a universal target. A useful report explains:

- whether latency changes under concurrency
- whether cache hits materially improve account-summary latency
- whether the worker keeps memory bounded for large files
- whether queue depth grows faster than workers drain it
- whether rate limiting behaves consistently across replicas
- which resource becomes the bottleneck first

## Submission Note

A technical walkthrough video is a separate deliverable. It should show the configuration, command, live load test, measured output, failure recovery, and analysis. This repository provides the test tooling and reporting structure but does not fabricate benchmark evidence.
