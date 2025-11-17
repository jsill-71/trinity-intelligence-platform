// Trinity Platform - Azure Infrastructure as Code
// Deploys complete Trinity Platform to Azure Container Apps

param location string = 'eastus'
param environmentName string = 'trinity-prod'
param acrName string = 'trinityacr'

// Container Apps Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${environmentName}-env'
  location: location
  properties: {
    daprAIConnectionString: ''
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// Log Analytics
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${environmentName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Azure Container Registry
resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// PostgreSQL Flexible Server
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-03-01-preview' = {
  name: '${environmentName}-postgres'
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: 'trinity'
    administratorLoginPassword: '<SECRET_FROM_KEYVAULT>'
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// PostgreSQL Database
resource postgresDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-03-01-preview' = {
  parent: postgres
  name: 'trinity'
}

// Azure Cache for Redis
resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: '${environmentName}-redis'
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

// Azure Service Bus (replaces NATS)
resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: '${environmentName}-servicebus'
  location: location
  sku: {
    name: 'Standard'
  }
}

// Service Bus Topics for event streams
resource githubEventsTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBus
  name: 'github-events'
}

resource ntaiEventsTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBus
  name: 'ntai-events'
}

resource gitCommitsTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBus
  name: 'git-commits'
}

// Cosmos DB for MongoDB API (replaces Neo4j)
resource cosmosdb 'Microsoft.DocumentDB/databaseAccounts@2023-09-15' = {
  name: '${environmentName}-cosmos'
  location: location
  kind: 'MongoDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    capabilities: [
      {
        name: 'EnableMongo'
      }
    ]
  }
}

// Key Vault for secrets
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: '${environmentName}-kv'
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
    enableRbacAuthorization: true
  }
}

// Storage Account for backups and models
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${environmentName}storage'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

// Container Apps - Event Collector
resource eventCollectorApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'event-collector'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        allowInsecure: false
      }
      secrets: [
        {
          name: 'postgres-password'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/postgres-password'
        }
        {
          name: 'servicebus-connection'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/servicebus-connection'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'event-collector'
          image: '${acr.properties.loginServer}/event-collector:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'SERVICEBUS_CONNECTION'
              secretRef: 'servicebus-connection'
            }
            {
              name: 'POSTGRES_URL'
              value: 'postgresql://trinity@${postgres.name}:${postgres.listKeys().primaryKey}@${postgres.properties.fullyQualifiedDomainName}:5432/trinity'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// Container Apps - RCA API
resource rcaApiApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'rca-api'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
      secrets: [
        {
          name: 'cosmos-connection'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/cosmos-connection'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'rca-api'
          image: '${acr.properties.loginServer}/rca-api:latest'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'COSMOS_CONNECTION'
              secretRef: 'cosmos-connection'
            }
            {
              name: 'VECTOR_SEARCH_URL'
              value: 'https://vector-search.${containerAppEnv.properties.defaultDomain}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 2
        maxReplicas: 20
      }
    }
  }
}

// Container Apps - Vector Search
resource vectorSearchApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'vector-search'
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: false
        targetPort: 8000
      }
      secrets: [
        {
          name: 'redis-key'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/redis-key'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'vector-search'
          image: '${acr.properties.loginServer}/vector-search:latest'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'REDIS_HOST'
              value: '${redis.name}.redis.cache.windows.net'
            }
            {
              name: 'REDIS_KEY'
              secretRef: 'redis-key'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

output eventCollectorUrl string = eventCollectorApp.properties.configuration.ingress.fqdn
output rcaApiUrl string = rcaApiApp.properties.configuration.ingress.fqdn
output vectorSearchUrl string = vectorSearchApp.properties.configuration.ingress.fqdn
