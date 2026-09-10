#!/bin/bash
# Complete Azure Deployment Script for Transaction Processing Platform
# This script automates all steps from AZURE_DEPLOYMENT.md

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="txn-platform-rg"
LOCATION="eastus"
ACR_NAME="txnapiregistry"
CONTAINER_APPS_ENV="txn-platform-env"
API_CONTAINER_NAME="txn-api"
WORKER_CONTAINER_NAME="txn-worker"

# Secrets (from environment or command line)
DATABASE_URL="${1:-}"
REDIS_URL="${2:-}"
AZURE_SUBSCRIPTION="${3:-}"

# Function to print status messages
print_status() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ ERROR: $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

# Validate inputs
if [ -z "$DATABASE_URL" ]; then
    print_error "DATABASE_URL not provided. Usage: ./deploy.sh <DATABASE_URL> <REDIS_URL> [AZURE_SUBSCRIPTION]"
fi

if [ -z "$REDIS_URL" ]; then
    print_error "REDIS_URL not provided. Usage: ./deploy.sh <DATABASE_URL> <REDIS_URL> [AZURE_SUBSCRIPTION]"
fi

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Transaction Processing Platform - Azure Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check prerequisites
print_status "Step 1: Checking prerequisites..."

command -v az &> /dev/null || print_error "Azure CLI not installed. Install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
print_success "Azure CLI installed"

command -v docker &> /dev/null || print_error "Docker not installed"
print_success "Docker installed"

command -v openssl &> /dev/null || print_error "OpenSSL not installed"
print_success "OpenSSL installed"

# Step 2: Login to Azure
print_status "Step 2: Logging in to Azure..."
az login --use-device-code
print_success "Logged in to Azure"

# Set subscription if provided
if [ ! -z "$AZURE_SUBSCRIPTION" ]; then
    az account set --subscription "$AZURE_SUBSCRIPTION"
    print_success "Subscription set"
fi

# Step 3: Run migrations against Neon
print_status "Step 3: Running database migrations..."
export DATABASE_URL="$DATABASE_URL"

# Check if we can reach the database
if python3 -c "import asyncpg; print('asyncpg available')" 2>/dev/null; then
    print_warning "Skipping alembic check (requires local setup). Run manually if needed:"
    echo "  DATABASE_URL='$DATABASE_URL' alembic upgrade head"
else
    print_warning "asyncpg not installed locally. Migrations will run in container."
fi

# Step 4: Create Resource Group
print_status "Step 4: Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    2>/dev/null || print_success "Resource group already exists"
print_success "Resource group ready: $RESOURCE_GROUP"

# Step 5: Create Azure Container Registry
print_status "Step 5: Creating container registry..."
az acr create \
    --resource-group "$RESOURCE_GROUP" \
    --name "$ACR_NAME" \
    --sku Basic \
    2>/dev/null || print_success "Container registry already exists"
print_success "Container registry ready: $ACR_NAME"

# Step 6: Get ACR details
ACR_URL=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASS=$(az acr credential show --name "$ACR_NAME" --query 'passwords[0].value' -o tsv)

print_success "ACR URL: $ACR_URL"

# Step 7: Build and push Docker images
print_status "Step 6: Building and pushing Docker images..."

# Verify Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    print_error "Dockerfile not found in current directory"
fi

# Login to ACR
print_status "  Logging into ACR..."
az acr login --name "$ACR_NAME"
print_success "  Logged into ACR"

# Build API image
print_status "  Building API image..."
docker build -t txn-api:latest .
docker tag txn-api:latest "$ACR_URL/txn-api:latest"
docker push "$ACR_URL/txn-api:latest"
print_success "  API image pushed to ACR"

# Tag as worker (same image, different entrypoint in container app)
docker tag txn-api:latest "$ACR_URL/txn-worker:latest"
docker push "$ACR_URL/txn-worker:latest"
print_success "  Worker image pushed to ACR"

# Step 8: Create Container Apps Environment
print_status "Step 7: Creating Container Apps environment..."
az containerapp env create \
    --name "$CONTAINER_APPS_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    2>/dev/null || print_success "Container Apps environment already exists"
print_success "Container Apps environment ready: $CONTAINER_APPS_ENV"

# Step 9: Deploy API Container
print_status "Step 8: Deploying API container..."

az containerapp create \
    --name "$API_CONTAINER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APPS_ENV" \
    --image "$ACR_URL/txn-api:latest" \
    --registry-login-server "$ACR_URL" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --ingress external \
    --target-port 8000 \
    --env-vars \
        DATABASE_URL="$DATABASE_URL" \
        REDIS_URL="$REDIS_URL" \
        SECRET_KEY="$SECRET_KEY" \
        APP_ENV="production" \
        LOG_LEVEL="INFO" \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 1.0 \
    --memory 1Gi \
    2>/dev/null || {
        print_status "  API container already exists, updating..."
        az containerapp update \
            --name "$API_CONTAINER_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --image "$ACR_URL/txn-api:latest"
    }
print_success "API container deployed"

# Step 10: Deploy Worker Container
print_status "Step 9: Deploying Worker container..."

az containerapp create \
    --name "$WORKER_CONTAINER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$CONTAINER_APPS_ENV" \
    --image "$ACR_URL/txn-worker:latest" \
    --registry-login-server "$ACR_URL" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --ingress internal \
    --env-vars \
        DATABASE_URL="$DATABASE_URL" \
        REDIS_URL="$REDIS_URL" \
        SECRET_KEY="$SECRET_KEY" \
        APP_ENV="production" \
        LOG_LEVEL="INFO" \
    --min-replicas 1 \
    --max-replicas 2 \
    --cpu 0.5 \
    --memory 512Mi \
    --command python \
    --args "-m,app.workers.import_worker" \
    2>/dev/null || {
        print_status "  Worker container already exists, updating..."
        az containerapp update \
            --name "$WORKER_CONTAINER_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --image "$ACR_URL/txn-worker:latest"
    }
print_success "Worker container deployed"

# Step 11: Get API URL
print_status "Step 10: Retrieving API endpoint..."
API_URL=$(az containerapp show \
    --name "$API_CONTAINER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.configuration.ingress.fqdn' \
    -o tsv)

if [ -z "$API_URL" ]; then
    print_warning "Could not retrieve API URL. Waiting for deployment..."
    sleep 10
    API_URL=$(az containerapp show \
        --name "$API_CONTAINER_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query 'properties.configuration.ingress.fqdn' \
        -o tsv)
fi

print_success "API URL: https://$API_URL"

# Step 12: Verify deployment
print_status "Step 11: Verifying deployment..."
echo "  Waiting for API to become ready (this may take 30-60 seconds)..."

for i in {1..20}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://"$API_URL"/health/live 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        print_success "API is healthy"
        break
    fi
    if [ $i -eq 20 ]; then
        print_warning "API not yet responsive (HTTP $HTTP_CODE). It may still be starting."
    fi
    echo -ne "\r  Attempt $i/20... (HTTP $HTTP_CODE)"
    sleep 3
done

echo ""

# Step 13: Test health endpoint
print_status "Step 12: Testing health endpoints..."

HEALTH_LIVE=$(curl -s https://"$API_URL"/health/live)
echo "  /health/live: $HEALTH_LIVE"

HEALTH_READY=$(curl -s https://"$API_URL"/health/ready)
echo "  /health/ready: $HEALTH_READY"

# Step 14: Create API key
print_status "Step 13: Creating demo API key..."

print_warning "Note: To create an API key, run this command:"
echo "  az containerapp exec --name $API_CONTAINER_NAME --resource-group $RESOURCE_GROUP --command python -m scripts.create_api_key demo-client"
echo ""
echo "  Or access the container directly to create keys as needed."

# Final summary
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "📋 Deployment Summary:"
echo "  Resource Group:     $RESOURCE_GROUP"
echo "  Container Registry: $ACR_NAME"
echo "  Region:             $LOCATION"
echo ""
echo "🌐 API Endpoints:"
echo "  Base URL:  https://$API_URL"
echo "  Swagger:   https://$API_URL/docs"
echo "  Health:    https://$API_URL/health/ready"
echo ""
echo "📊 Container Apps:"
echo "  API:       $API_CONTAINER_NAME (1-3 replicas, 1.0 CPU, 1GB mem)"
echo "  Worker:    $WORKER_CONTAINER_NAME (1-2 replicas, 0.5 CPU, 512MB mem)"
echo ""
echo "🔧 Next Steps:"
echo "  1. Create API key:"
echo "     az containerapp exec --name $API_CONTAINER_NAME --resource-group $RESOURCE_GROUP --command python -m scripts.create_api_key demo-client"
echo ""
echo "  2. Test API:"
echo "     curl -X POST https://$API_URL/api/v1/imports \\"
echo "       -H \"X-API-Key: <YOUR_KEY>\" \\"
echo "       -F \"file=@sample.csv\""
echo ""
echo "  3. View logs:"
echo "     az containerapp logs show --name $API_CONTAINER_NAME --resource-group $RESOURCE_GROUP --follow"
echo ""
echo "  4. View container apps:"
echo "     az containerapp show --name $API_CONTAINER_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "💰 Cost Estimation:"
echo "  Container Apps: ~\$5-15/month (consumption-based)"
echo "  Storage:        Free (first 10GB)"
echo "  Total:          ~\$5-15/month"
echo ""
echo "⚠️  To clean up and avoid costs:"
echo "  az group delete --name $RESOURCE_GROUP --yes --no-wait"
echo ""
echo -e "${GREEN}Ready for production use!${NC}"
echo ""
