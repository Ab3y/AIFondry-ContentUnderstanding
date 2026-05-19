// az deployment group create --resource-group <rg-name> --template-file main.bicep --parameters main.bicepparam

using './main.bicep'

// Name of the Azure AI Services account to create. Update this to a globally unique resource name.
param resourceName = '<your-resource-name>'

// Region for the deployment. Keep this in a Content Understanding supported region.
param location = 'eastus'

// Optional: override this if you want the custom subdomain to differ from the resource name.
// param customSubDomainName = '<your-custom-subdomain>'
