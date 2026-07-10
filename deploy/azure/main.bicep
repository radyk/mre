// MRE API — Azure Container Apps deployment (docs/07 Phase 2, W4 / session 2.4 CU3).
//
// Provider-swap boundary: EVERYTHING Azure-specific lives in deploy/azure/. The
// application image is provider-agnostic (reads only MRE_* config, no Azure
// SDK). This template supplies the Azure equivalents of the compose stack:
//   - managed TLS ingress            == the Caddy proxy locally
//   - Azure Files on an encrypted     == the mre-data volume locally
//     storage account
//   - a Container App secret sourced   == environment-injected secrets locally
//     from Key Vault
//
// Deploy with deploy/azure/deploy.sh (builds/pushes the image, then `az deployment`).

@description('Base name for all resources (lowercase, <= 20 chars).')
param name string = 'mre'

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Fully qualified container image, e.g. <acr>.azurecr.io/mre-api:<tag>.')
param image string

@description('Container registry login server (e.g. <acr>.azurecr.io).')
param registryServer string

@description('Registry username (or use managed identity in a hardening pass).')
param registryUsername string

@description('Registry password.')
@secure()
param registryPassword string

@description('Optional Anthropic API key for the M10 explainer LLM path. Injected as a secret, never baked into the image. Leave empty to run without the LLM.')
@secure()
param anthropicApiKey string = ''

var storageName = toLower('${name}sa${uniqueString(resourceGroup().id)}')
var shareName = '${name}-data'
var envName = '${name}-env'
var appName = '${name}-api'

// ---------------------------------------------------------------------------
// Encryption at rest: Azure Storage is always encrypted (Microsoft-managed
// keys by default; customer-managed keys are a later hardening decision, see
// docs/08 §2). This file share backs the single MRE_DATA_ROOT volume.
// ---------------------------------------------------------------------------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    encryption: {
      services: {
        file: { enabled: true }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

resource fileServices 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: fileServices
  name: shareName
  properties: {
    shareQuota: 100
  }
}

// ---------------------------------------------------------------------------
// Container Apps managed environment + the storage link for the Azure Files
// volume (registry / snapshots / evidence all live under it).
// ---------------------------------------------------------------------------
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {}
}

resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: shareName
  properties: {
    azureFile: {
      accountName: storage.name
      accountKey: storage.listKeys().keys[0].value
      shareName: shareName
      accessMode: 'ReadWrite'
    }
  }
}

// ---------------------------------------------------------------------------
// The API container app. Managed TLS ingress terminates HTTPS (the cloud
// equivalent of the local Caddy proxy) and forwards to the plaintext :8000.
// ---------------------------------------------------------------------------
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        // Platform-managed certificate on the default *.azurecontainerapps.io
        // FQDN; a custom domain + managed cert is a later config step.
        allowInsecure: false
      }
      registries: [
        {
          server: registryServer
          username: registryUsername
          passwordSecretRef: 'registry-password'
        }
      ]
      secrets: concat(
        [ { name: 'registry-password', value: registryPassword } ],
        empty(anthropicApiKey) ? [] : [ { name: 'anthropic-api-key', value: anthropicApiKey } ]
      )
    }
    template: {
      containers: [
        {
          name: appName
          image: image
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: concat(
            [
              { name: 'MRE_DATA_ROOT', value: '/data' }
              { name: 'PYTHONHASHSEED', value: '0' }
            ],
            empty(anthropicApiKey) ? [] : [ { name: 'ANTHROPIC_API_KEY', secretRef: 'anthropic-api-key' } ]
          )
          volumeMounts: [
            { volumeName: 'data', mountPath: '/data' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 15
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'data'
          storageType: 'AzureFile'
          storageName: shareName
        }
      ]
      scale: {
        // Single tenant by construction (docs/08 §4): pin one replica so the
        // SQLite registry and the file volume have a single writer.
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [ envStorage ]
}

output apiFqdn string = app.properties.configuration.ingress.fqdn
output apiUrl string = 'https://${app.properties.configuration.ingress.fqdn}'
