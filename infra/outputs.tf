output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "acr_name" {
  value = azurerm_container_registry.main.name
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "aca_name" {
  value = azurerm_container_app.mcp.name
}

output "aca_fqdn" {
  value = azurerm_container_app.mcp.ingress[0].fqdn
}

output "mcp_endpoint" {
  value = "https://${azurerm_container_app.mcp.ingress[0].fqdn}/mcp"
}
