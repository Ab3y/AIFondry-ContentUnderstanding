targetScope = 'resourceGroup'

// Template metadata for discoverability and quick reference.
metadata description = 'Deploys an Azure AI Services account configured for Azure AI Foundry Content Understanding demos.'
metadata contentUnderstandingOverview = 'https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview'
metadata supportedRegions = [
  'eastus'
  'eastus2'
  'westus'
  'westus3'
  'westeurope'
  'northeurope'
  'swedencentral'
  'uksouth'
  'southcentralus'
  'southeastasia'
  'australiaeast'
  'japaneast'
]

@description('Name of the Azure AI Services account to create.')
param resourceName string

@description('Azure region for the deployment. Content Understanding currently supports a limited set of regions.')
param location string = 'eastus'

// Content Understanding requires a custom subdomain so callers can use the account-specific endpoint.
@description('Custom subdomain used to build the Azure AI Services endpoint URL. Defaults to the resource name.')
param customSubDomainName string = resourceName

// Use AIServices because Content Understanding is provisioned from the Azure AI Services multi-service account type.
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-12-01' = {
  name: resourceName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    // S0 is the standard SKU used for Azure AI Services and is appropriate for demo deployments.
    name: 'S0'
  }
  properties: {
    // Required so the deployed resource has the account-specific endpoint expected by Content Understanding.
    customSubDomainName: customSubDomainName
    publicNetworkAccess: 'Enabled'
    // Keep local auth enabled so API keys can be used by demos and quickstarts.
    disableLocalAuth: false
  }
}

@description('Content Understanding endpoint URL for the deployed Azure AI Services account.')
output endpointUrl string = 'https://${customSubDomainName}.cognitiveservices.azure.com'

@description('Resource ID of the deployed Azure AI Services account.')
output resourceId string = aiServicesAccount.id

@description('Resource name of the deployed Azure AI Services account.')
output deployedResourceName string = aiServicesAccount.name
