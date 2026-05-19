variable "resource_name" {
  description = "Name of the Azure AI Services resource to deploy. This value is also used for the custom subdomain."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the Azure resource group that will contain the Content Understanding resource."
  type        = string
  default     = "rg-content-understanding"
}

variable "location" {
  description = "Azure region for the Content Understanding deployment."
  type        = string
  default     = "eastus"

  validation {
    condition = contains([
      "eastus",
      "eastus2",
      "westus",
      "westus3",
      "westeurope"
    ], lower(var.location))
    error_message = "Location must be one of: eastus, eastus2, westus, westus3, westeurope."
  }
}
