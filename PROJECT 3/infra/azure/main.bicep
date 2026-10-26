// ==============================================================================
// Azure Infrastructure as Code (Bicep) - Enterprise GenAI Deployment
// Deploys:
// 1. Log Analytics Workspace (Telemetry & Splunk forwarder)
// 2. Azure Container Registry (ACR)
// 3. Azure Key Vault (Secrets Management)
// 4. User-Assigned Managed Identity (Least-Privilege AcrPull)
// 5. Azure Container Apps Environment & Ingress-Enabled Container App
// ==============================================================================

@description('Azure deployment region')
param location string = resourceGroup().location

@description('Unique application name prefix')
param appPrefix string = 'genai-rag'

@description('Target environment')
param environment string = 'prod'

@description('Container Image Tag')
param imageTag string = 'latest'

@description('API Key Secret for Key Vault')
@secure()
param apiKeySecret string

var acrName = '${replace(appPrefix, '-', '')}${environment}acr'
var logWorkspaceName = '${appPrefix}-${environment}-logs'
var containerEnvName = '${appPrefix}-${environment}-env'
var containerAppName = '${appPrefix}-${environment}-app'
var keyVaultName = '${replace(appPrefix, '-', '')}${environment}kv'
var identityName = '${appPrefix}-${environment}-id'

// 1. Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// 2. Azure Container Registry (ACR)
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

// 3. User-Assigned Managed Identity for Least-Privilege Pull
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

// AcrPull Role Definition ID: 7f951dda-4ed3-4680-a7ca-43fe172d538d
resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, managedIdentity.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// 4. Azure Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: false
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: managedIdentity.properties.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
    ]
  }
}

resource apiKeySecretResource 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'API-KEY'
  properties: {
    value: apiKeySecret
  }
}

// 5. Container Apps Managed Environment
resource containerAppEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// 6. Azure Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: acr.properties.loginServer
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'api-key-secret'
          keyVaultUrl: '${keyVault.properties.vaultUri}secrets/API-KEY'
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'genai-rag'
          image: '${acr.properties.loginServer}/enterprise-genai-rag:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'APP_ENV'
              value: 'production'
            },
            {
              name: 'API_KEY'
              secretRef: 'api-key-secret'
            },
            {
              name: 'TOP_K'
              value: '3'
            },
            {
              name: 'SIMILARITY_THRESHOLD'
              value: '0.15'
            },
            {
              name: 'ENABLE_TELEMETRY'
              value: 'true'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              periodSeconds: 30
              failureThreshold: 3
            },
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              periodSeconds: 15
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output acrLoginServer string = acr.properties.loginServer
output keyVaultUri string = keyVault.properties.vaultUri
