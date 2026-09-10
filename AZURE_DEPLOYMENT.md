# Azure Deployment Guide

## Live Deployment URLs
After deployment, your endpoints will be available at:
- **API Base:** `https://txn-api-<hash>.eastus.azurecontainerapps.io`
- **Swagger UI:** `https://txn-api-<hash>.eastus.azurecontainerapps.io/docs`
- **Health Check:** `https://txn-api-<hash>.eastus.azurecontainerapps.io/health/ready`

## Azure Services Used

| Service | Purpose | Tier | Cost |
|---------|---------|------|------|
| Azure Container Apps | API + Worker hosting | Consumption | $0-50/mo* |
| Azure Container Registry | Docker image storage | Basic | Free (first 10GB) |
| Neon PostgreSQL | Database | Free | $0 |
| Upstash Redis | Cache + queue | Free | $0 (first 10K requests) |

*Cost depends on CPU time and memory usage; free tier available for light loads.

## Why Azure Container Apps?
- **Serverless scaling** - min/max replicas configured per container
- **Native health check integration** - readiness probe on `/health/ready`
- **No VM management** - fully managed runtime, pay per resource used
- **Free consumption plan** - ideal for internship projects and prototypes
- **Separate containers** - API and Worker deploy independently, scale independently
- **Environment variables** - secrets managed securely without hardcoding

## Architecture Diagram

```
Internet
    ↓
Azure Container Apps (Load Balancer)
    ├─ API Container (FastAPI, 1-3 replicas, external ingress)
    │   ├─ Port 8000 exposed
    │   └─ CPU: 0.5-1, Memory: 512MB-1GB
    │
    └─ Worker Container (Python worker, 1-2 replicas, no ingress)
        ├─ Internal use only
        └─ CPU: 0.25-0.5, Memory: 256MB-512MB
            ↓
        Shared Resources:
        ├─ Neon PostgreSQL (primary data store)
        │   └─ Connection pooling via PgBouncer
        └─ Upstash Redis (cache + rate limit + job queue)
            └─ TLS 1.2+ connection
```

## Pre-Deployment Checklist

- [ ] Azure free trial account or paying account
- [ ] Azure CLI installed: `az --version`
- [ ] Docker installed locally (for building images)
- [ ] Neon PostgreSQL account created (neon.tech)
- [ ] Upstash Redis account created (upstash.com)

## Step-by-Step Deployment

### 1. Create Neon PostgreSQL Database (5 min)

1. Go to neon.tech → Sign up → New Project
2. Choose: PostgreSQL 15, Region: US East 1
3. Note the **Connection String** (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb`)
4. Copy this as `DATABASE_URL` environment variable

### 2. Create Upstash Redis Database (5 min)

1. Go to upstash.com → Sign up → Create Database
2. Choose: Redis, Region: US East 1
3. Under "REST API" tab, copy the `REDIS_URL` (looks like `rediss://default:pass@xxx.upstash.io:6379`)
4. Copy this as `REDIS_URL` environment variable

### 3. Create Resource Group in Azure (2 min)

```bash
az login
az group create --name txn-platform-rg --location eastus
```

### 4. Create Azure Container Registry (3 min)

```bash
az acr create --resource-group txn-platform-rg \
  --name txnapiregistry --sku Basic
```

### 5. Build and Push Docker Images (10 min)

```bash
# Login to ACR
az acr login --name txnapiregistry

# Get ACR URL
ACR_URL=$(az acr show --name txnapiregistry --query loginServer -o tsv)

# Build API image
docker build -t txn-api:latest .
docker tag txn-api:latest $ACR_URL/txn-api:latest
docker push $ACR_URL/txn-api:latest

# Build worker image (Dockerfile same, just different entrypoint)
docker tag txn-api:latest $ACR_URL/txn-worker:latest
docker push $ACR_URL/txn-worker:latest
```

### 6. Run Migrations Against Neon (5 min)

```bash
export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"
pip install alembic asyncpg sqlalchemy
alembic upgrade head
```

### 7. Create Container Apps Environment (3 min)

```bash
az containerapp env create \
  --name txn-platform-env \
  --resource-group txn-platform-rg \
  --location eastus
```

### 8. Deploy API Container (5 min)

```bash
ACR_URL=$(az acr show --name txnapiregistry --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name txnapiregistry --query username -o tsv)
ACR_PASS=$(az acr credential show --name txnapiregistry --query passwords[0].value -o tsv)

az containerapp create \
  --name txn-api \
  --resource-group txn-platform-rg \
  --environment txn-platform-env \
  --image $ACR_URL/txn-api:latest \
  --registry-login-server $ACR_URL \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --ingress external \
  --target-port 8000 \
  --env-vars \
    DATABASE_URL="$DATABASE_URL" \
    REDIS_URL="$REDIS_URL" \
    SECRET_KEY="$(openssl rand -hex 32)" \
    APP_ENV="production" \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 1Gi \
  --health-probe "GET /health/ready"
```

### 9. Deploy Worker Container (5 min)

```bash
az containerapp create \
  --name txn-worker \
  --resource-group txn-platform-rg \
  --environment txn-platform-env \
  --image $ACR_URL/txn-worker:latest \
  --registry-login-server $ACR_URL \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --ingress internal \
  --env-vars \
    DATABASE_URL="$DATABASE_URL" \
    REDIS_URL="$REDIS_URL" \
    SECRET_KEY="$(openssl rand -hex 32)" \
    APP_ENV="production" \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 512Mi \
  --command "python" \
  --args "-m" "app.workers.import_worker"
```

### 10. Verify Deployment (5 min)

```bash
# Get API URL
API_URL=$(az containerapp show --name txn-api \
  --resource-group txn-platform-rg \
  --query properties.configuration.ingress.fqdn -o tsv)

echo "API URL: https://$API_URL"

# Test health
curl https://$API_URL/health/ready
# Expected: {"status":"ready","postgresql":"ok","redis":"ok"}

# View logs
az containerapp logs show --name txn-api \
  --resource-group txn-platform-rg --follow

# View container details
az containerapp show --name txn-api --resource-group txn-platform-rg
```

### 11. Create API Key on Azure (3 min)

```bash
az containerapp exec \
  --name txn-api \
  --resource-group txn-platform-rg \
  --command python -m scripts.create_api_key demo-client
```

## Secret Management

### Option 1: Azure Key Vault (Recommended for Production)

```bash
# Create Key Vault
az keyvault create --name txn-platform-kv \
  --resource-group txn-platform-rg --location eastus

# Store secrets
az keyvault secret set --vault-name txn-platform-kv \
  --name database-url --value "$DATABASE_URL"

az keyvault secret set --vault-name txn-platform-kv \
  --name redis-url --value "$REDIS_URL"

# Update container app to reference secrets
# (Use @Microsoft.KeyVault(SecretUri=...) syntax in env vars)
```

### Option 2: Environment Variables (Current Setup)

All secrets passed as environment variables during container creation.
**Advantage**: Simple, no additional services.
**Disadvantage**: Less secure for production.

**Note**: Never commit secrets to git. Always use environment variables or Key Vault.

## Scaling Configuration

### Auto-Scaling Rules

The containers use Azure Container Apps' built-in auto-scaling:

**API Container**:
- Min replicas: 1
- Max replicas: 3
- Scales based on: HTTP requests/sec, CPU, memory
- Scale trigger: >60% CPU or >1000 requests/sec

**Worker Container**:
- Min replicas: 1
- Max replicas: 2
- Scales based on: CPU, memory (or configure for Redis queue depth)
- Manual scaling recommended for consistent processing

### Manual Scaling

```bash
az containerapp update --name txn-api \
  --resource-group txn-platform-rg \
  --set properties.template.scale.minReplicas=2 \
                properties.template.scale.maxReplicas=5
```

## Monitoring & Logging

### Container Logs

```bash
# Stream API logs
az containerapp logs show --name txn-api \
  --resource-group txn-platform-rg --follow

# Stream worker logs
az containerapp logs show --name txn-worker \
  --resource-group txn-platform-rg --follow
```

### Application Insights (Optional)

```bash
az monitor app-insights component create \
  --app txn-platform-ai \
  --location eastus \
  --resource-group txn-platform-rg

# Pass APPLICATIONINSIGHTS_CONNECTION_STRING in env vars
```

## Database Connectivity

### Connection Pooling

Neon includes PgBouncer for connection pooling. Use the pooling connection string:
```
postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
```

### Connection Issues?

If containers can't reach Postgres:
1. Verify Neon IP allowlist includes Container Apps public IPs
2. Enable "Enhanced SSL" in Neon database settings
3. Check firewall rules in Neon dashboard

## Troubleshooting

### Health Check Failing

If `curl https://<url>/health/ready` returns an error:

```bash
# Check container logs
az containerapp logs show --name txn-api \
  --resource-group txn-platform-rg --follow

# Verify secrets are passed correctly
az containerapp show --name txn-api \
  --resource-group txn-platform-rg | jq '.properties.template.containers[0].env'

# Test locally first
docker run -e DATABASE_URL="..." -e REDIS_URL="..." <image>
```

### Out of Memory (OOM)

If containers crash with memory errors:

```bash
# Increase memory allocation
az containerapp update --name txn-api \
  --resource-group txn-platform-rg \
  --set properties.template.containers[0].resources.cpu=1.0 \
                properties.template.containers[0].resources.memory=2Gi
```

### Database Connection Timeout

- Verify Neon IP allowlist
- Check DATABASE_URL format and credentials
- Test locally: `DATABASE_URL=$URL alembic current`

## Cost Estimation

| Service | Usage | Estimated Cost |
|---------|-------|-----------------|
| Container Apps | 1-3 replicas, 1 CPU, 1GB | $5-15/mo |
| Container Registry | <10GB images | Free |
| Neon PostgreSQL | <50GB, moderate usage | Free |
| Upstash Redis | <10K requests | Free |
| **Total** | **Typical internship** | **$0-15/mo** |

## Teardown (To Avoid Costs)

```bash
# Delete entire resource group
az group delete --name txn-platform-rg --yes --no-wait

# Verify deletion
az group list | grep txn-platform-rg
```

## Deployment Automation Script

Save as `deploy.sh`:

```bash
#!/bin/bash
set -e

# Configuration
ACR_NAME="txnapiregistry"
RESOURCE_GROUP="txn-platform-rg"
LOCATION="eastus"
DATABASE_URL="${DATABASE_URL:?ERROR: DATABASE_URL not set}"
REDIS_URL="${REDIS_URL:?ERROR: REDIS_URL not set}"
SECRET_KEY=$(openssl rand -hex 32)

echo "🚀 Deploying Transaction Platform to Azure..."

# Login
az login

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create ACR
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic

# Build and push images
ACR_URL=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
docker build -t txn-api:latest .
docker tag txn-api:latest $ACR_URL/txn-api:latest
docker push $ACR_URL/txn-api:latest

# Get ACR credentials
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Create Container Apps environment
az containerapp env create \
  --name txn-platform-env \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# Deploy API
az containerapp create \
  --name txn-api \
  --resource-group $RESOURCE_GROUP \
  --environment txn-platform-env \
  --image $ACR_URL/txn-api:latest \
  --registry-login-server $ACR_URL \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --ingress external \
  --target-port 8000 \
  --env-vars DATABASE_URL="$DATABASE_URL" REDIS_URL="$REDIS_URL" SECRET_KEY="$SECRET_KEY" \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 1.0 \
  --memory 1Gi

# Deploy Worker
az containerapp create \
  --name txn-worker \
  --resource-group $RESOURCE_GROUP \
  --environment txn-platform-env \
  --image $ACR_URL/txn-api:latest \
  --registry-login-server $ACR_URL \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --ingress internal \
  --env-vars DATABASE_URL="$DATABASE_URL" REDIS_URL="$REDIS_URL" SECRET_KEY="$SECRET_KEY" \
  --command python -m app.workers.import_worker \
  --min-replicas 1 \
  --max-replicas 2 \
  --cpu 0.5 \
  --memory 512Mi

# Get and display URLs
API_URL=$(az containerapp show --name txn-api --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
echo "✅ Deployment complete!"
echo "API URL: https://$API_URL"
echo "Swagger: https://$API_URL/docs"
```

## Next Steps

1. Configure CI/CD pipeline (GitHub Actions → Azure)
2. Set up Application Insights for monitoring
3. Configure auto-scaling based on Redis queue depth
4. Implement backup strategy for PostgreSQL
5. Add custom domain (CNAME record)

---

**Last Updated**: 2026-09-09  
**Status**: ✅ Ready for Deployment  
**Estimated Deploy Time**: 30-45 minutes  
**Support**: Refer to Azure Container Apps documentation
