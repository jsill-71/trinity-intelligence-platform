# Trinity Platform - Azure Deployment Guide

**Target:** Azure Container Apps with managed services
**Region:** East US (primary)
**Estimated Cost:** $200-400/month for pilot

---

## Architecture Changes for Azure

### Infrastructure Replacements

**Local → Azure:**

| Local Service | Azure Managed Service | Reason |
|---------------|----------------------|--------|
| NATS JetStream | Azure Service Bus (Standard) | Managed message bus, HA, Azure-native |
| Neo4j | Cosmos DB (MongoDB API) | Fully managed, global dist, Azure-native |
| PostgreSQL | Azure Database for PostgreSQL Flexible | Managed, HA, backups, scaling |
| Redis | Azure Cache for Redis | Managed, HA, geo-replication |

### Service Deployment

**All 22 application services → Azure Container Apps:**
- Auto-scaling (1-20 replicas based on load)
- Zero-downtime deployments
- Integrated with Azure Monitor
- Managed identity for secrets
- HTTPS by default

---

## Deployment Steps

### Prerequisites

1. **Azure CLI installed**
   ```bash
   az --version
   ```

2. **Azure subscription**
   ```bash
   az login
   az account set --subscription "<subscription-id>"
   ```

3. **Docker installed**
   ```bash
   docker --version
   ```

### Step 1: Create Resource Group

```bash
az group create \
  --name trinity-platform-rg \
  --location eastus
```

### Step 2: Deploy Infrastructure (Bicep)

```bash
cd azure/
az deployment group create \
  --resource-group trinity-platform-rg \
  --template-file infrastructure.bicep
```

**Creates:**
- Container Apps Environment
- Azure Container Registry
- PostgreSQL Flexible Server
- Azure Cache for Redis
- Azure Service Bus
- Cosmos DB
- Key Vault
- Storage Account

### Step 3: Build and Push Docker Images

```bash
./deploy.sh
```

**OR manually:**

```bash
ACR_NAME="trinityacr"
az acr login --name $ACR_NAME

# Build all 22 services
for service in event-collector kg-projector rca-api investigation-api vector-search user-management audit-service notification-service ml-training agent-orchestrator workflow-engine data-aggregator metrics-collector api-gateway alert-manager query-optimizer backup-service health-monitor cache-service rate-limiter real-time-processor scheduler-service; do
  docker build -t $ACR_NAME.azurecr.io/$service:latest -f services/$service/Dockerfile .
  docker push $ACR_NAME.azurecr.io/$service:latest
done
```

### Step 4: Configure Secrets in Key Vault

```bash
KV_NAME="trinity-prod-kv"

# Database secrets
az keyvault secret set --vault-name $KV_NAME --name postgres-password --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name $KV_NAME --name cosmos-key --value "<from-cosmos-account>"
az keyvault secret set --vault-name $KV_NAME --name redis-key --value "<from-redis-instance>"

# Service Bus
az keyvault secret set --vault-name $KV_NAME --name servicebus-connection --value "<connection-string>"

# Application secrets
az keyvault secret set --vault-name $KV_NAME --name jwt-secret --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name $KV_NAME --name webhook-secret --value "$(openssl rand -base64 32)"
az keyvault secret set --vault-name $KV_NAME --name anthropic-api-key --value "<your-anthropic-key>"
```

### Step 5: Deploy Container Apps

**Using GitHub Actions (Recommended):**
1. Configure `AZURE_CREDENTIALS` secret in GitHub
2. Push to master/main branch
3. GitHub Actions automatically deploys

**Using Azure CLI:**
```bash
# Deploy each service
az containerapp create \
  --name event-collector \
  --resource-group trinity-platform-rg \
  --environment trinity-prod-env \
  --image trinityacr.azurecr.io/event-collector:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 10 \
  --secrets postgres-pwd=keyvaultref:$KV_URI/secrets/postgres-password,IdentityRef:$IDENTITY_ID \
  --env-vars POSTGRES_URL=secretref:postgres-pwd
```

### Step 6: Verify Deployment

```bash
# Get service URLs
az containerapp show --name event-collector --resource-group trinity-platform-rg --query properties.configuration.ingress.fqdn -o tsv

# Test health endpoints
EVENT_COLLECTOR_URL=$(az containerapp show --name event-collector --resource-group trinity-platform-rg --query properties.configuration.ingress.fqdn -o tsv)
curl https://$EVENT_COLLECTOR_URL/health
```

---

## Code Changes for Azure

### Environment Detection

Services auto-detect Azure vs local:

```python
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT", "false").lower() == "true"

if AZURE_DEPLOYMENT:
    # Use Azure Service Bus
    from azure_adapter import AzureServiceBusAdapter
    message_bus = AzureServiceBusAdapter()
else:
    # Use NATS
    from nats.aio.client import Client as NATS
    message_bus = NATS()
```

### Required Dependencies

Add to `requirements.txt`:
```
azure-servicebus==7.11.0
azure-cosmos==4.5.1
azure-identity==1.15.0
azure-keyvault-secrets==4.7.0
```

---

## Scaling Configuration

### Auto-Scaling Rules

**Event Collector:**
- Min: 1, Max: 10
- Scale on: HTTP concurrency (100 req/instance)

**RCA API:**
- Min: 2, Max: 20
- Scale on: HTTP concurrency + CPU (>70%)

**Vector Search:**
- Min: 1, Max: 5
- Scale on: Memory (>80%)

**API Gateway:**
- Min: 3, Max: 30
- Scale on: HTTP requests per second

---

## Monitoring

### Azure Monitor Integration

**Metrics Collected:**
- Container CPU/Memory usage
- HTTP request rate/latency
- Service Bus queue depth
- Cosmos DB RU consumption
- Redis cache hit rate

**Alerts Configured:**
- High error rate (>5%)
- High latency (>2s p95)
- Service unavailable
- Database connection issues

**Log Analytics Queries:**
```kusto
ContainerAppConsoleLogs_CL
| where ContainerAppName_s == "event-collector"
| where Log_s contains "ERROR"
| project TimeGenerated, Log_s
```

---

## Cost Estimate

**Infrastructure (per month):**
- Container Apps Environment: $0 (free tier)
- 26 Container Apps @ $0.000012/vCPU-second: ~$200
- PostgreSQL Flexible (B1ms): $12
- Cosmos DB (400 RU/s): $24
- Redis (Basic C0): $17
- Service Bus (Standard): $10
- Storage (LRS): $5
- Key Vault: $0.03

**Total:** ~$270-400/month (varies with load)

---

## High Availability

**Multi-Region Setup:**
1. Deploy to East US (primary)
2. Deploy to West US (secondary)
3. Azure Front Door for global load balancing
4. Cosmos DB global distribution
5. Geo-redundant backups

**Estimated Additional Cost:** +60% (~$430-640/month total)

---

## Security

**Managed Identity:**
- All services use managed identity
- No passwords in code or env vars
- Key Vault references for secrets

**Network Security:**
- Private endpoints for databases
- VNet integration for Container Apps
- NSG rules for service-to-service communication
- Public internet access only via API Gateway

**Compliance:**
- Encryption at rest (all Azure services)
- Encryption in transit (TLS 1.2+)
- Audit logging to Log Analytics
- GDPR-compliant data residency

---

## Deployment Checklist

**Before First Deployment:**
- [ ] Azure subscription created
- [ ] Service principal for GitHub Actions
- [ ] ACR created
- [ ] Resource group created
- [ ] All secrets generated and stored in Key Vault
- [ ] DNS configured (optional)

**For Each Deployment:**
- [ ] Docker images built
- [ ] Images pushed to ACR
- [ ] Infrastructure deployed (Bicep)
- [ ] Container Apps updated
- [ ] Health checks passing
- [ ] Integration tests passing
- [ ] Monitoring configured

**Post-Deployment:**
- [ ] Configure alerts
- [ ] Set up backup jobs
- [ ] Test failover
- [ ] Load testing
- [ ] Security scan

---

## Rollback Procedure

```bash
# Rollback to previous revision
az containerapp revision list \
  --name event-collector \
  --resource-group trinity-platform-rg

# Activate previous revision
az containerapp revision activate \
  --name event-collector \
  --resource-group trinity-platform-rg \
  --revision <previous-revision-name>
```

---

## Files Created

1. **azure/infrastructure.bicep** - Complete infrastructure as code
2. **azure/deploy.sh** - Deployment automation script
3. **.github/workflows/azure-deploy.yml** - CI/CD pipeline
4. **azure/container-apps-manifest.yaml** - Kubernetes-style manifest
5. **services/*/azure_adapter.py** - Azure service adapters
6. **azure/AZURE_DEPLOYMENT_GUIDE.md** - This file

---

## Next Steps

1. Run `az login`
2. Run `./azure/deploy.sh`
3. Wait ~15 minutes for infrastructure
4. Verify health endpoints
5. Configure DNS (optional)
6. Run integration tests
7. Monitor in Azure Portal

**Trinity Platform will be production-ready on Azure.**
