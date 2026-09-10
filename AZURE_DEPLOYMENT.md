# Azure Deployment Guide

This repository deploys two separate Azure Container Apps workloads:

- `txn-api`: public FastAPI service with external HTTP ingress on port 8000.
- `txn-worker`: private background consumer with no HTTP ingress.

Both workloads use images from Azure Container Registry and connect to external Neon PostgreSQL and Upstash Redis services.

## Verified Deployment

- Region: `koreacentral` because it is allowed by the active Azure for Students policy.
- Resource group: `txn-platform-rg`
- Container Registry: `txnapiregistry`
- Container Apps environment: `txn-platform-env`
- API URL: `https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io`
- Swagger: `https://txn-api.blackocean-56128bc6.koreacentral.azurecontainerapps.io/docs`

The URL above is an environment-specific deployment value. A new environment can produce a different hostname.

## Architecture

```text
Client
  |
  v
Azure Container Apps: txn-api  -- external :8000
  |                         \
  |                          \ Redis Streams/cache/rate limits
  v                           \
Neon PostgreSQL                 Azure Container Apps: txn-worker -- no ingress
                                  |
                                  +-- consumes imports:queue
```

## Prerequisites

- Azure CLI with the Container Apps extension
- Docker Desktop
- An authenticated Azure subscription
- Neon PostgreSQL URL
- Upstash Redis URL

Check tools:

```powershell
az --version
docker --version
az account show
```

## Secure Deployment

Do not place credentials in the script or commit them to Git. Set them only in the current shell:

```powershell
$env:DATABASE_URL="postgresql://user:password@host/database?sslmode=require"
$env:REDIS_URL="rediss://default:password@host:6379"
.\deploy-fixed-final.ps1
```

The script rejects local Docker hostnames, strips the shell-sensitive Neon `channel_binding` parameter, and passes the resulting values through Container Apps secrets. Rotate credentials if they have been exposed.

## What The Canonical Script Does

`deploy-fixed-final.ps1` performs these operations:

1. Reuses the current Azure CLI login or starts device-code login.
2. Reuses or creates the resource group and registry.
3. Enables ACR credentials for image pulls.
4. Builds the API image from `Dockerfile`.
5. Builds the worker image from `Dockerfile.worker`.
6. Tags both images with a UTC timestamp instead of reusing `latest`.
7. Pushes both images to ACR.
8. Reuses or creates the Container Apps environment.
9. Recreates the API with external ingress and target port 8000.
10. Recreates the worker with no HTTP ingress.
11. Verifies Azure provisioning and running states.
12. Prints the API and Swagger URLs.

Run it from the repository root:

```powershell
Set-Location .\transaction-platform-master
$env:DATABASE_URL="postgresql://..."
$env:REDIS_URL="rediss://..."
.\deploy-fixed-final.ps1
```

## Runtime Configuration

The API and worker receive these values through Container Apps secret references:

- `DATABASE_URL`
- `REDIS_URL`
- generated `SECRET_KEY`

Non-secret values include:

- `APP_ENV=production`
- `LOG_LEVEL=INFO`

The application normalizes Neon URL parameters for asyncpg and uses TLS when `sslmode=require` is supplied.

## Verification

```powershell
$api = "https://<api-fqdn>"
curl.exe -fsS "$api/"
curl.exe -fsS "$api/health/live"
curl.exe -fsS "$api/health/ready"

az containerapp revision list -n txn-api -g txn-platform-rg -o table
az containerapp revision list -n txn-worker -g txn-platform-rg -o table
```

Expected states are `Healthy`, `Running`, and `Provisioned` for both revisions. The worker has no browser URL by design.

## Database Migration

Migrations are part of the local Compose workflow. For a new external database, run Alembic using the same `DATABASE_URL` before accepting traffic:

```powershell
$env:DATABASE_URL="postgresql://user:password@host/database?sslmode=require"
python -m alembic -c migrations/alembic.ini upgrade head
```

## Logging And Monitoring

The application writes structured logs for API requests, imports, worker lifecycle, retries, and failures. Azure Container Apps provides revision and replica state. The installed Azure CLI version may have issues with `az containerapp logs show` on Express environments; use the Azure portal or Container Apps log stream endpoint if that command fails.

Recommended production additions:

- Azure Log Analytics and Application Insights
- alerts for readiness failures, crash loops, latency, and queue growth
- Azure Blob Storage for uploaded files
- managed identity and Key Vault instead of ACR admin credentials

## Scaling

API and worker are independently deployable. The API uses a minimum of one replica and HTTP scaling. The worker uses a minimum of one replica and can be scaled independently. Redis consumer groups allow multiple workers to share queue work.

## Cost And Teardown

The deployment uses Consumption Container Apps, Basic ACR, and free-tier external data services where available. Costs depend on usage and subscription terms.

Remove the resource group when the environment is no longer needed:

```powershell
az group delete --name txn-platform-rg --yes --no-wait
```
