# 🏗️ Infrastructure - Deploy Content Understanding on Azure

## Overview

This folder contains Infrastructure as Code for provisioning the Azure resource used by this repo: an **Azure AI Services / AI Foundry account** configured for **Content Understanding**.

The templates deploy:

- An Azure AI Services account with `kind = "AIServices"`
- SKU `S0`
- A **custom subdomain** so the Content Understanding endpoint is account-specific
- A **system-assigned managed identity**
- **Public network access enabled**
- **Local authentication enabled** so you can use API keys with the demos and quickstart

> Notes:
> - The **Bicep** deployment targets an **existing resource group**.
> - The **Terraform** deployment creates both the **resource group** and the AI Services account.
> - These templates provision the resource, but they do **not** create the required model deployments automatically.

## Prerequisites

Before deploying, make sure you have:

1. An **Azure subscription**
2. The **Azure CLI** installed and authenticated with `az login`
3. One of the following:
   - **Bicep CLI** (or Azure CLI with Bicep support)
   - **Terraform**

## Option A: Deploy with Bicep

The Bicep files are in `infra\bicep`.

1. Open `infra\bicep\main.bicepparam`
2. Update these values:
   - `resourceName` = globally unique Azure AI Services resource name
   - `location` = supported Content Understanding region
   - Optionally set `customSubDomainName` if you do not want it to match `resourceName`
3. Make sure your target resource group already exists
4. Run the deployment:

```powershell
az deployment group create --resource-group <resource-group-name> --template-file .\infra\bicep\main.bicep --parameters .\infra\bicep\main.bicepparam
```

After deployment, note the endpoint output. It will be in this format:

```text
https://<custom-subdomain>.cognitiveservices.azure.com
```

## Option B: Deploy with Terraform

The Terraform files are in `infra\terraform`.

1. Open a terminal at the repo root
2. Change into the Terraform folder:

```powershell
cd .\infra\terraform
```

3. Initialize Terraform:

```powershell
terraform init
```

4. Preview the deployment:

```powershell
terraform plan -var="resource_name=my-foundry-resource" -var="resource_group_name=rg-content-understanding" -var="location=eastus"
```

5. Apply the deployment:

```powershell
terraform apply -var="resource_name=my-foundry-resource" -var="resource_group_name=rg-content-understanding" -var="location=eastus"
```

Terraform outputs include:

- `endpoint`
- `resource_id`
- `resource_name`

> Note: `variables.tf` currently validates `location` against `eastus`, `eastus2`, `westus`, `westus3`, and `westeurope`. If you want to use another supported Content Understanding region, update that validation block first.

## Post-Deployment Setup

1. Get the endpoint and key from the Azure Portal, or use Azure CLI:

```powershell
az cognitiveservices account show --resource-group <resource-group-name> --name <resource-name> --query properties.endpoint -o tsv
az cognitiveservices account keys list --resource-group <resource-group-name> --name <resource-name>
```

2. Configure `.env` in the repo root. You can start from `.env.template`:

```powershell
copy .env.template .env
```

Then set:

```env
CONTENTUNDERSTANDING_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com
CONTENTUNDERSTANDING_KEY=<your-api-key>
```

3. Enable model deployments in **Content Understanding Settings**:
   - https://contentunderstanding.ai.azure.com/settings
   - Add your deployed AI Foundry / AI Services resource
   - Enable the required models

4. Required models:
   - `gpt-4.1`
   - `gpt-4.1-mini`
   - `text-embedding-3-large`

## Supported Regions

Content Understanding supports these regions:

- `eastus`
- `eastus2`
- `westus`
- `westus3`
- `westeurope`
- `northeurope`
- `swedencentral`
- `uksouth`
- `southcentralus`
- `southeastasia`
- `australiaeast`
- `japaneast`

## Resources

- [ARM template reference: Microsoft.CognitiveServices/accounts](https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/accounts)
- [Content Understanding overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [Language and region support](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/language-region-support)

## See Also

- [Main README](../README.md) - Project overview, prerequisites, and full documentation links
- [Quickstart Demo](../quickstart/README.md) - Run your first demo in 2 minutes
- [Demo Walkthrough Scripts](../demos/README.md) - Progressive 3-step walkthrough
- [Model Explanation](../CU-Model-Explanation.md) - Why each AI model is needed
