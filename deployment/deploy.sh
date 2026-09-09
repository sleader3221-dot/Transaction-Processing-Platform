#!/usr/bin/env bash
set -euo pipefail

RESOURCE_GROUP="txn-platform-rg"
LOCATION="eastus"
ACR_NAME="txnplatform$(date +%s | tail -c6)"
ENV_NAME="txn-env"
APP_NAME_API="txn-api"
APP_NAME_WORKER="txn-worker"

DATABASE_URL="${DATABASE_URL:?Set DATABASE_URL (Neon connection string)}"
REDIS_URL="${REDIS_URL:?Set REDIS_URL (Upstash Redis URL)}"
SECRET_KEY="${SECRET_KEY:?Set SECRET_KEY}"

echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

echo "Creating ACR..."
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true

ACR_SERVER=$(az acr show --name "$ACR_NAME" \
  --query loginServer --output tsv)

echo "Building and pushing images..."
az acr build \
  --registry "$ACR_NAME" \
  --image txn-api:latest \
  --file Dockerfile .

az acr build \
  --registry "$ACR_NAME" \
  --image txn-worker:latest \
  --file Dockerfile .

echo "Creating Container Apps environment..."
az containerapp env create \
  --name "$ENV_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION"

ACR_USER=$(az acr credential show --name "$ACR_NAME" \
  --query username --output tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" \
  --query "passwords[0].value" --output tsv)

COMMON_VARS=(
  "DATABASE_URL=$DATABASE_URL"
  "REDIS_URL=$REDIS_URL"
  "APP_ENV=production"
  "LOG_LEVEL=INFO"
  "SECRET_KEY=$SECRET_KEY"
  "UPLOAD_DIR=/app/uploads"
)

echo "Deploying API..."
az containerapp create \
  --name "$APP_NAME_API" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENV_NAME" \
  --image "$ACR_SERVER/txn-api:latest" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 \
  --memory 1Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --command "uvicorn" "app.main:app" "--host" "0.0.0.0" "--port" "8000" \
  --env-vars "${COMMON_VARS[@]}"

API_URL=$(az containerapp show \
  --name "$APP_NAME_API" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)

echo "API URL: https://$API_URL"

echo "Deploying Worker..."
az containerapp create \
  --name "$APP_NAME_WORKER" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "$ENV_NAME" \
  --image "$ACR_SERVER/txn-worker:latest" \
  --registry-server "$ACR_SERVER" \
  --registry-username "$ACR_USER" \
  --registry-password "$ACR_PASS" \
  --ingress none \
  --cpu 0.5 \
  --memory 1Gi \
  --min-replicas 1 \
  --max-replicas 2 \
  --command "python" "-m" "app.workers.import_worker" \
  --env-vars "${COMMON_VARS[@]}"

echo ""
echo "Deployment complete!"
echo "  API:     https://$API_URL"
echo "  Swagger: https://$API_URL/docs"
echo ""
echo "Run migrations against Neon:"
echo "  DATABASE_URL=\$DATABASE_URL alembic upgrade head"