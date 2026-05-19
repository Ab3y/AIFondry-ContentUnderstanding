terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# Azure AI Foundry Content Understanding requires an Azure AI Services multi-service account.
# The Cognitive Services resource kind must be "AIServices" so the account supports the
# Content Understanding capability. Using another kind (for example, OpenAI or TextAnalytics)
# will not provision a compatible endpoint for this service.
#
# Supported regions include eastus, eastus2, westus, westus3, westeurope, and other regions
# listed in the official documentation:
# https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview
resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_cognitive_account" "content_understanding" {
  name                = var.resource_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name

  kind     = "AIServices"
  sku_name = "S0"

  custom_subdomain_name         = var.resource_name
  public_network_access_enabled = true
  local_auth_enabled            = true

  identity {
    type = "SystemAssigned"
  }

  tags = {
    workload = "content-understanding"
  }
}
