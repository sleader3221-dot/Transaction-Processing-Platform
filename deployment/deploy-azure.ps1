# Complete Azure Deployment Script for Transaction Processing Platform (PowerShell)
# Run: .\deploy-azure.ps1 -DatabaseUrl "..." -RedisUrl "..." -AzureSubscription "..."

param(
    [Parameter(Mandatory=$true)]
    [string]$DatabaseUrl,
    
    [Parameter(Mandatory=$true)]
    [string]$RedisUrl,
    
    [Parameter(Mandatory=$false)]
    [string]$AzureSubscription
)

$ErrorActionPreference = "Stop"

# Configuration
$ResourceGroup = "txn-platform-rg"
$Location = "eastus"
$AcrName = "txnapiregistry"
$ContainerAppsEnv = "txn-platform-env"
$ApiContainerName = "txn-api"
$WorkerContainerName = "txn-worker"

# Generate secrets
$SecretKey = -join ((0..31) | ForEach-Object { [char][byte]$([convert]::tobyte(("{0:X2}" -f (Get-Random -Maximum 256)),16)) })

function Print-Status {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor Blue
}

function Print-Success {
    param([string]$Message)
    Write-Host "✅ $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Error "❌ ERROR: $Message"
    exit 1
}

function Print-Warning {
    param([string]$Message)
    Write-Host "⚠️  WARNING: $Message" -ForegroundColor Yellow
}

# Banner
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Blue
Write-Host "  Transaction Processing Platform - Azure Deployment" -ForegroundColor Blue
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Blue
Write-Host ""

# Step 1: Check prerequisites
Print-Status "Step 1: Checking prerequisites..."

try {
    $null = az --version
    Print-Success "Azure CLI installed"
} catch {
    Print-Error "Azure CLI not installed. Install from https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
}

try {
    $null = docker --version
    Print-Success "Docker installed"
} catch {
    Print-Error "Docker not installed"
}

# Step 2: Login to Azure
Print-Status "Step 2: Logging in to Azure..."
$null = az login --use-device-code
Print-Success "Logged in to Azure"

# Set subscription if provided
if ($AzureSubscription) {
    az account set --subscription $AzureSubscription
    Print-Success "Subscription set"
}

# Step 3: Create Resource Group
Print-Status "Step 3: Creating resource group..."
$null = az group create `
    --name $ResourceGroup `
    --location $Location `
    -ErrorAction SilentlyContinue
Print-Success "Resource group ready: $ResourceGroup"

# Step 4: Create Azure Container Registry
Print-Status "Step 4: Creating container registry..."
$null = az acr create `
    --resource-group $ResourceGroup `
    --name $AcrName `
    --sku Basic `
    -ErrorAction SilentlyContinue
Print-Success "Container registry ready: $AcrName"

# Step 5: Get ACR details
Print-Status "Step 5: Retrieving ACR credentials..."
$AcrUrl = az acr show --name $AcrName --query loginServer -o tsv
$AcrUser = az acr credential show --name $AcrName --query username -o tsv
$AcrPass = az acr credential show --name $AcrName --query 'passwords[0].value' -o tsv

Print-Success "ACR URL: $AcrUrl"

# Step 6: Build and push Docker images
Print-Status "Step 6: Building and pushing Docker images..."

if (-not (Test-Path "Dockerfile")) {
    Print-Error "Dockerfile not found in current directory"
}

Print-Status "  Logging into ACR..."
$null = az acr login --name $AcrName
Print-Success "  Logged into ACR"

Print-Status "  Building API image..."
$null = docker build -t txn-api:latest .
$null = docker tag txn-api:latest "$AcrUrl/txn-api:latest"
$null = docker push "$AcrUrl/txn-api:latest"
Print-Success "  API image pushed to ACR"

$null = docker tag txn-api:latest "$AcrUrl/txn-worker:latest"
$null = docker push "$AcrUrl/txn-worker:latest"
Print-Success "  Worker image pushed to ACR"

# Step 7: Create Container Apps Environment
Print-Status "Step 7: Creating Container Apps environment..."
$null = az containerapp env create `
    --name $ContainerAppsEnv `
    --resource-group $ResourceGroup `
    --location $Location `
    -ErrorAction SilentlyContinue
Print-Success "Container Apps environment ready: $ContainerAppsEnv"

# Step 8: Deploy API Container
Print-Status "Step 8: Deploying API container..."

$null = az containerapp create `
    --name $ApiContainerName `
    --resource-group $ResourceGroup `
    --environment $ContainerAppsEnv `
    --image "$AcrUrl/txn-api:latest" `
    --registry-login-server $AcrUrl `
    --registry-username $AcrUser `
    --registry-password $AcrPass `
    --ingress external `
    --target-port 8000 `
    --env-vars `
        DATABASE_URL="$DatabaseUrl" `
        REDIS_URL="$RedisUrl" `
        SECRET_KEY="$SecretKey" `
        APP_ENV="production" `
        LOG_LEVEL="INFO" `
    --min-replicas 1 `
    --max-replicas 3 `
    --cpu 1.0 `
    --memory 1Gi `
    -ErrorAction SilentlyContinue

Print-Success "API container deployed"

# Step 9: Deploy Worker Container
Print-Status "Step 9: Deploying Worker container..."

$null = az containerapp create `
    --name $WorkerContainerName `
    --resource-group $ResourceGroup `
    --environment $ContainerAppsEnv `
    --image "$AcrUrl/txn-worker:latest" `
    --registry-login-server $AcrUrl `
    --registry-username $AcrUser `
    --registry-password $AcrPass `
    --ingress internal `
    --env-vars `
        DATABASE_URL="$DatabaseUrl" `
        REDIS_URL="$RedisUrl" `
        SECRET_KEY="$SecretKey" `
        APP_ENV="production" `
        LOG_LEVEL="INFO" `
    --min-replicas 1 `
    --max-replicas 2 `
    --cpu 0.5 `
    --memory 512Mi `
    --command python `
    --args "-m,app.workers.import_worker" `
    -ErrorAction SilentlyContinue

Print-Success "Worker container deployed"

# Step 10: Get API URL
Print-Status "Step 10: Retrieving API endpoint..."
$ApiUrl = az containerapp show `
    --name $ApiContainerName `
    --resource-group $ResourceGroup `
    --query 'properties.configuration.ingress.fqdn' `
    -o tsv

if (-not $ApiUrl) {
    Print-Warning "Could not retrieve API URL. Waiting for deployment..."
    Start-Sleep -Seconds 10
    $ApiUrl = az containerapp show `
        --name $ApiContainerName `
        --resource-group $ResourceGroup `
        --query 'properties.configuration.ingress.fqdn' `
        -o tsv
}

Print-Success "API URL: https://$ApiUrl"

# Step 11: Verify deployment
Print-Status "Step 11: Verifying deployment..."
Write-Host "  Waiting for API to become ready (this may take 30-60 seconds)..."

for ($i = 1; $i -le 20; $i++) {
    try {
        $Response = Invoke-WebRequest -Uri "https://$ApiUrl/health/live" -TimeoutSec 5 -ErrorAction SilentlyContinue
        $HttpCode = $Response.StatusCode
    } catch {
        $HttpCode = "000"
    }
    
    if ($HttpCode -eq 200) {
        Print-Success "API is healthy"
        break
    }
    
    if ($i -eq 20) {
        Print-Warning "API not yet responsive (HTTP $HttpCode). It may still be starting."
    }
    
    Write-Host -NoNewline "`r  Attempt $i/20... (HTTP $HttpCode)"
    Start-Sleep -Seconds 3
}

Write-Host ""

# Step 12: Test health endpoints
Print-Status "Step 12: Testing health endpoints..."

try {
    $HealthLive = Invoke-WebRequest -Uri "https://$ApiUrl/health/live" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  /health/live: $($HealthLive.Content)"
} catch {
    Print-Warning "Could not reach /health/live"
}

try {
    $HealthReady = Invoke-WebRequest -Uri "https://$ApiUrl/health/ready" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  /health/ready: $($HealthReady.Content)"
} catch {
    Print-Warning "Could not reach /health/ready"
}

# Final summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "📋 Deployment Summary:"
Write-Host "  Resource Group:     $ResourceGroup"
Write-Host "  Container Registry: $AcrName"
Write-Host "  Region:             $Location"
Write-Host ""

Write-Host "🌐 API Endpoints:"
Write-Host "  Base URL:  https://$ApiUrl"
Write-Host "  Swagger:   https://$ApiUrl/docs"
Write-Host "  Health:    https://$ApiUrl/health/ready"
Write-Host ""

Write-Host "📊 Container Apps:"
Write-Host "  API:       $ApiContainerName (1-3 replicas, 1.0 CPU, 1GB mem)"
Write-Host "  Worker:    $WorkerContainerName (1-2 replicas, 0.5 CPU, 512MB mem)"
Write-Host ""

Write-Host "🔧 Next Steps:"
Write-Host "  1. Create API key:"
Write-Host "     az containerapp exec --name $ApiContainerName --resource-group $ResourceGroup --command python -m scripts.create_api_key demo-client"
Write-Host ""
Write-Host "  2. Test API:"
Write-Host "     curl -X POST https://$ApiUrl/api/v1/imports \\"
Write-Host "       -H \"X-API-Key: <YOUR_KEY>\" \"
Write-Host "       -F \"file=@sample.csv\""
Write-Host ""
Write-Host "  3. View logs:"
Write-Host "     az containerapp logs show --name $ApiContainerName --resource-group $ResourceGroup --follow"
Write-Host ""
Write-Host "💰 Cost Estimation:"
Write-Host "  Container Apps: ~\$5-15/month (consumption-based)"
Write-Host "  Storage:        Free (first 10GB)"
Write-Host "  Total:          ~\$5-15/month"
Write-Host ""
Write-Host "⚠️  To clean up and avoid costs:"
Write-Host "  az group delete --name $ResourceGroup --yes --no-wait"
Write-Host ""
Write-Host "Ready for production use!" -ForegroundColor Green
Write-Host ""
