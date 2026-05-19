# terraform init
# terraform plan -var="resource_name=my-foundry-resource"
# terraform apply -var="resource_name=my-foundry-resource"

output "endpoint" {
  description = "Content Understanding endpoint URL."
  value       = azurerm_cognitive_account.content_understanding.endpoint
}

output "resource_id" {
  description = "Azure resource ID for the deployed AI Services account."
  value       = azurerm_cognitive_account.content_understanding.id
}

output "resource_name" {
  description = "Name of the deployed AI Services account."
  value       = azurerm_cognitive_account.content_understanding.name
}
