<#
==============================================================================
PowerShell Azure Container Apps Automated Deployment Script
==============================================================================
#>

param (
    [string]$ResourceGroup = "rg-genai-prod",
    [string]$Location = "eastus",
    [string]$AppPrefix = "genai-rag",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Deploying Enterprise GenAI RAG Application to Azure Container Apps" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Create Resource Group
Write-Host "[1/4] Ensuring Resource Group exists: $ResourceGroup ($Location)..." -ForegroundColor Yellow
az group create --name $ResourceGroup --location $Location --output table

# 2. Deploy Bicep template
Write-Host "[2/4] Deploying Bicep Template (Key Vault, ACR, Container Apps Env)..." -ForegroundColor Yellow
$deployJson = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file infra/azure/main.bicep `
    --parameters appPrefix=$AppPrefix apiKeySecret="sk-enterprise-rag-prod-secret-key-2026" imageTag=$ImageTag `
    --output json | ConvertFrom-Json

$acrServer = $deployJson.properties.outputs.acrLoginServer.value
$appFqdn = $deployJson.properties.outputs.fqdn.value

# 3. Build & Push Image
Write-Host "[3/4] Building and pushing Docker container to $acrServer..." -ForegroundColor Yellow
az acr build --registry $acrServer --image "enterprise-genai-rag:$ImageTag" .

# 4. Update Container App
Write-Host "[4/4] Updating Container App deployment..." -ForegroundColor Yellow
az containerapp update `
    --name "$AppPrefix-prod-app" `
    --resource-group $ResourceGroup `
    --image "$acrServer/enterprise-genai-rag:$ImageTag" `
    --output table

Write-Host "=================================================================" -ForegroundColor Green
Write-Host " Deployment Succeeded!" -ForegroundColor Green
Write-Host " URL: https://$appFqdn" -ForegroundColor Green
Write-Host " Swagger: https://$appFqdn/docs" -ForegroundColor Green
Write-Host " Dashboard: https://$appFqdn/dashboard" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
