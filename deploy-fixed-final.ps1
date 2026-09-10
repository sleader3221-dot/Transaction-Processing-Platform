$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Azure Deployment - Fixed Version" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Use a region allowed by the Azure for Students policy.
$ResourceGroup = "txn-platform-rg"
$Location = "koreacentral"
$AcrName = "txnapiregistry"
$ContainerAppsEnv = "txn-platform-env"
$ApiContainerName = "txn-api"
$WorkerContainerName = "txn-worker"
$ImageTag = Get-Date -Format "yyyyMMddHHmmss"

$DatabaseUrl = $env:DATABASE_URL
$RedisUrl = $env:REDIS_URL
$DatabaseUrl = $DatabaseUrl -replace '&channel_binding=require', ''
if (-not $DatabaseUrl -or -not $RedisUrl) {
  Write-Host "ERROR: Set DATABASE_URL and REDIS_URL before running deployment." -ForegroundColor Red
  exit 1
}
if ($DatabaseUrl -match '@postgres(:|/)' -or $RedisUrl -match '://redis(:|/)') {
  Write-Host "ERROR: DATABASE_URL and REDIS_URL must point to reachable cloud services, not Docker Compose hosts." -ForegroundColor Red
  exit 1
}
$SecretKey = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })

Write-Host "Checking prerequisites..." -ForegroundColor Yellow
az --version 2>&1 | Select-Object -First 1
docker --version
Write-Host ""

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  AZURE AUTHENTICATION" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

$AzureAccount = az account show --output json 2>$null | ConvertFrom-Json
if (-not $AzureAccount) {
  Write-Host "No active Azure login found. Starting device-code login..." -ForegroundColor Yellow
  az login --use-device-code
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Azure login failed." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "Using active Azure account: $($AzureAccount.user.name)" -ForegroundColor Green
  Write-Host "Subscription: $($AzureAccount.name) ($($AzureAccount.id))" -ForegroundColor Green
}

Write-Host ""
Write-Host "[Step 1] Creating resource group in $Location..." -ForegroundColor Yellow
$ResourceGroupExists = az group exists --name $ResourceGroup 2>$null
if ($ResourceGroupExists -ne "true") {
  az group create --name $ResourceGroup --location $Location -o none
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not create resource group $ResourceGroup." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "Using existing resource group $ResourceGroup." -ForegroundColor Green
}

Write-Host "[Step 2] Registering resource providers..." -ForegroundColor Yellow
az provider register -n Microsoft.OperationalInsights --wait -o none 2>&1
az provider register -n Microsoft.App --wait -o none 2>&1
az provider register -n Microsoft.ContainerRegistry --wait -o none 2>&1

Write-Host "[Step 3] Creating container registry..." -ForegroundColor Yellow
$ExistingAcr = az acr show --name $AcrName --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ExistingAcr) {
  az acr create --resource-group $ResourceGroup --name $AcrName --sku Basic --location $Location -o none
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not create container registry $AcrName in $Location." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "Using existing container registry $AcrName." -ForegroundColor Green
}

az acr update --name $AcrName --resource-group $ResourceGroup --admin-enabled true -o none
if ($LASTEXITCODE -ne 0) {
  Write-Host "ERROR: Could not enable registry admin credentials." -ForegroundColor Red
  exit 1
}

Write-Host "[Step 4] Getting registry credentials..." -ForegroundColor Yellow
$AcrUrl = az acr show --name $AcrName --resource-group $ResourceGroup --query loginServer -o tsv 2>$null
$AcrUser = az acr credential show --name $AcrName --resource-group $ResourceGroup --query username -o tsv 2>$null
$AcrPass = az acr credential show --name $AcrName --resource-group $ResourceGroup --query 'passwords[0].value' -o tsv 2>$null

if ($LASTEXITCODE -ne 0 -or -not $AcrUrl -or -not $AcrUser -or -not $AcrPass -or $AcrUrl -match '^ERROR') {
    Write-Host "ERROR: Could not get ACR credentials. Registry may not exist." -ForegroundColor Red
    exit 1
}

Write-Host "Registry: $AcrUrl" -ForegroundColor Green
Write-Host ""

Write-Host "[Step 5] Building Docker image..." -ForegroundColor Yellow
cd "C:\Users\Tanvi Technology\Downloads\transaction-platform-master\transaction-platform-master"
docker build -t txn-api:latest . 2>&1 | Select-Object -Last 5
docker build -f Dockerfile.worker -t txn-worker:latest . 2>&1 | Select-Object -Last 5
$ExistingWorker = az containerapp show --name $WorkerContainerName --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $ExistingWorker) {
    az containerapp delete --name $WorkerContainerName --resource-group $ResourceGroup --yes
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not remove the previous worker deployment." -ForegroundColor Red
        exit 1
    }
}


Write-Host ""
Write-Host "[Step 6] Tagging images..." -ForegroundColor Yellow
docker tag txn-api:latest "$AcrUrl/txn-api:$ImageTag" 2>&1
docker tag txn-worker:latest "$AcrUrl/txn-worker:$ImageTag" 2>&1
Write-Host "OK" -ForegroundColor Green

Write-Host "[Step 7] Logging into registry..." -ForegroundColor Yellow
az acr login --name $AcrName --resource-group $ResourceGroup 2>&1 | Select-Object -First 1

Write-Host "[Step 8] Pushing images..." -ForegroundColor Yellow
docker push "$AcrUrl/txn-api:$ImageTag" 2>&1 | Select-Object -Last 3
docker push "$AcrUrl/txn-worker:$ImageTag" 2>&1 | Select-Object -Last 3

Write-Host ""
Write-Host "[Step 9] Creating Container Apps environment..." -ForegroundColor Yellow
$ExistingEnvironment = az containerapp env show --name $ContainerAppsEnv --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ExistingEnvironment) {
  az containerapp env create --name $ContainerAppsEnv --resource-group $ResourceGroup --location $Location -o none
  if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not create Container Apps environment $ContainerAppsEnv in $Location." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "Using existing Container Apps environment $ContainerAppsEnv." -ForegroundColor Green
}

Write-Host ""
Write-Host "[Step 10] Deploying API container..." -ForegroundColor Yellow

$ExistingApi = az containerapp show --name $ApiContainerName --resource-group $ResourceGroup --query name -o tsv 2>$null
if ($LASTEXITCODE -eq 0 -and $ExistingApi) {
    az containerapp delete --name $ApiContainerName --resource-group $ResourceGroup --yes
      if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not remove the previous API deployment." -ForegroundColor Red
        exit 1
      }
}
az containerapp create `
  --name $ApiContainerName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppsEnv `
  --image "$AcrUrl/txn-api:$ImageTag" `
  --registry-server $AcrUrl `
  --registry-username $AcrUser `
  --registry-password $AcrPass `
  --ingress external `
  --target-port 8000 `
  --secrets `
    db-url="$DatabaseUrl" `
    redis-url="$RedisUrl" `
    secret-key="$SecretKey" `
  --env-vars `
    DATABASE_URL=secretref:db-url `
    REDIS_URL=secretref:redis-url `
    SECRET_KEY=secretref:secret-key `
    APP_ENV=production `
    LOG_LEVEL=INFO `
  --min-replicas 1 `
  --max-replicas 3 `
  --cpu 1.0 `
  --memory 2Gi `
  -o none
$ApiStatus = az containerapp show --name $ApiContainerName --resource-group $ResourceGroup --query '{provisioning:properties.provisioningState,running:properties.runningStatus}' -o json 2>$null | ConvertFrom-Json
if (-not $ApiStatus -or $ApiStatus.provisioning -ne "Succeeded" -or $ApiStatus.running -ne "Running") {
    Write-Host "ERROR: API container deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host "OK" -ForegroundColor Green
Write-Host ""

Write-Host "[Step 11] Deploying Worker container..." -ForegroundColor Yellow

az containerapp create `
  --name $WorkerContainerName `
  --resource-group $ResourceGroup `
  --environment $ContainerAppsEnv `
  --image "$AcrUrl/txn-worker:$ImageTag" `
  --registry-server $AcrUrl `
  --registry-username $AcrUser `
  --registry-password $AcrPass `
  --secrets `
    db-url="$DatabaseUrl" `
    redis-url="$RedisUrl" `
    secret-key="$SecretKey" `
  --env-vars `
    DATABASE_URL=secretref:db-url `
    REDIS_URL=secretref:redis-url `
    SECRET_KEY=secretref:secret-key `
    APP_ENV=production `
    LOG_LEVEL=INFO `
  --min-replicas 1 `
  --max-replicas 2 `
  --cpu 0.25 `
  --memory 0.5Gi `
  -o none
$WorkerState = az containerapp revision list --name $WorkerContainerName --resource-group $ResourceGroup --query '[0].properties.runningState' -o tsv 2>$null
if ($WorkerState -ne "Running") {
    Write-Host "ERROR: Worker container deployment failed." -ForegroundColor Red
    exit 1
}

Write-Host "OK" -ForegroundColor Green
Write-Host ""

Write-Host "[Step 12] Getting API URL..." -ForegroundColor Yellow
$ApiUrl = az containerapp show --name $ApiContainerName --resource-group $ResourceGroup --query 'properties.configuration.ingress.fqdn' -o tsv 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ApiUrl) {
  Write-Host "ERROR: Could not retrieve the API URL." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Your Live API:" -ForegroundColor Cyan
Write-Host "  https://$ApiUrl" -ForegroundColor Yellow
Write-Host ""
Write-Host "Swagger UI:" -ForegroundColor Cyan
Write-Host "  https://$ApiUrl/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Open: https://$ApiUrl/docs" -ForegroundColor White
Write-Host "  2. Test your API!" -ForegroundColor White
Write-Host ""
