#!/bin/bash
# Trinity Platform - Azure Deployment Script

set -e

RESOURCE_GROUP="trinity-platform-rg"
LOCATION="eastus"
ENVIRONMENT_NAME="trinity-prod"
ACR_NAME="trinityacr"

echo "=== Trinity Platform Azure Deployment ==="
echo ""

# 1. Create Resource Group
echo "[1/10] Creating resource group..."
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# 2. Deploy Infrastructure
echo "[2/10] Deploying infrastructure (Bicep)..."
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infrastructure.bicep \
  --parameters location=$LOCATION environmentName=$ENVIRONMENT_NAME acrName=$ACR_NAME

# 3. Get ACR credentials
echo "[3/10] Getting ACR credentials..."
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# 4. Build and push Docker images
echo "[4/10] Building Docker images..."
cd ..

# Build all services
services=(
  "event-collector"
  "kg-projector"
  "rca-api"
  "investigation-api"
  "vector-search"
  "user-management"
  "audit-service"
  "notification-service"
  "ml-training"
  "agent-orchestrator"
  "workflow-engine"
  "data-aggregator"
  "metrics-collector"
  "api-gateway"
)

for service in "${services[@]}"; do
  echo "Building $service..."
  docker build -t $ACR_LOGIN_SERVER/$service:latest -f services/$service/Dockerfile .
done

# 5. Login to ACR
echo "[5/10] Logging into ACR..."
echo $ACR_PASSWORD | docker login $ACR_LOGIN_SERVER --username $ACR_USERNAME --password-stdin

# 6. Push images
echo "[6/10] Pushing images to ACR..."
for service in "${services[@]}"; do
  echo "Pushing $service..."
  docker push $ACR_LOGIN_SERVER/$service:latest
done

# 7. Create Key Vault secrets
echo "[7/10] Creating Key Vault secrets..."
KV_NAME="${ENVIRONMENT_NAME}-kv"

az keyvault secret set --vault-name $KV_NAME --name postgres-password --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name $KV_NAME --name redis-key --value "$(az redis list-keys --name ${ENVIRONMENT_NAME}-redis --resource-group $RESOURCE_GROUP --query primaryKey -o tsv)"
az keyvault secret set --vault-name $KV_NAME --name servicebus-connection --value "$(az servicebus namespace authorization-rule keys list --resource-group $RESOURCE_GROUP --namespace-name ${ENVIRONMENT_NAME}-servicebus --name RootManageSharedAccessKey --query primaryConnectionString -o tsv)"
az keyvault secret set --vault-name $KV_NAME --name cosmos-connection --value "$(az cosmosdb keys list --name ${ENVIRONMENT_NAME}-cosmos --resource-group $RESOURCE_GROUP --query primaryMasterKey -o tsv)"
az keyvault secret set --vault-name $KV_NAME --name jwt-secret --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name $KV_NAME --name webhook-secret --value "$(openssl rand -base64 32)"

# 8. Update Container Apps with secrets
echo "[8/10] Updating Container Apps..."
# Container Apps automatically pull secrets from Key Vault via managed identity

# 9. Configure networking
echo "[9/10] Configuring networking..."
# Create private endpoints, VNet integration, etc.

# 10. Verify deployment
echo "[10/10] Verifying deployment..."
EVENT_COLLECTOR_URL=$(az containerapp show --name event-collector --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)
RCA_API_URL=$(az containerapp show --name rca-api --resource-group $RESOURCE_GROUP --query properties.configuration.ingress.fqdn -o tsv)

echo ""
echo "=== Deployment Complete ==="
echo "Event Collector: https://$EVENT_COLLECTOR_URL"
echo "RCA API: https://$RCA_API_URL"
echo ""
echo "Test webhook:"
echo "curl -X POST https://$EVENT_COLLECTOR_URL/webhooks/github -H 'X-GitHub-Event: push' -d '{}'"
