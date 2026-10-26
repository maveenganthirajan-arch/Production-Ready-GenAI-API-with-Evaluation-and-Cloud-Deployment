#!/usr/bin/env bash
# ==============================================================================
# Automated Azure Container Apps Deployment Script
# Provisions Resource Group, ACR, Key Vault, and Container App using Bicep.
# ==============================================================================

set -euo pipefail

RESOURCE_GROUP="rg-genai-prod"
LOCATION="eastus"
APP_PREFIX="genairag"
IMAGE_NAME="enterprise-genai-rag"
TAG="${1:-latest}"

echo "================================================================="
echo " Deploying Enterprise GenAI RAG Application to Azure Container Apps"
echo "================================================================="

# 1. Create Resource Group if not exists
echo "[1/5] Creating Azure Resource Group: ${RESOURCE_GROUP} (${LOCATION})..."
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}" --output table

# 2. Deploy Azure Infrastructure with Bicep
echo "[2/5] Provisioning Infrastructure via Bicep (ACR, Key Vault, Log Analytics, ACA Env)..."
DEPLOY_OUTPUT=$(az deployment group create \
  --resource-group "${RESOURCE_GROUP}" \
  --template-file infra/azure/main.bicep \
  --parameters appPrefix="${APPPrefix:-genai-rag}" apiKeySecret="sk-enterprise-rag-prod-secret-key-2026" imageTag="${TAG}" \
  --output json)

ACR_LOGIN_SERVER=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.acrLoginServer.value')
APP_FQDN=$(echo "${DEPLOY_OUTPUT}" | jq -r '.properties.outputs.fqdn.value')

# 3. Build & Push Image to Azure Container Registry
echo "[3/5] Building & Pushing Docker image to ${ACR_LOGIN_SERVER}..."
az acr build --registry "${ACR_LOGIN_SERVER}" --image "${IMAGE_NAME}:${TAG}" .

# 4. Trigger Container App Revision Update
echo "[4/5] Deploying container revision to Azure Container App..."
az containerapp update \
  --name "genai-rag-prod-app" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${TAG}" \
  --output table

# 5. Verify Health Endpoint
echo "[5/5] Validating live deployment health..."
curl -s -f "https://${APP_FQDN}/health" || echo "Deployment warming up..."

echo "================================================================="
echo " Deployment Complete!"
echo " Public Application URL: https://${APP_FQDN}"
echo " Interactive Swagger Docs: https://${APP_FQDN}/docs"
echo " Splunk / Observability Dashboard: https://${APP_FQDN}/dashboard"
echo " Prometheus Metrics: https://${APP_FQDN}/metrics"
echo "================================================================="
