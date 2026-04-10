resource "azurerm_search_service" "main" {
  name                         = "ais-${var.prefix}-search"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  sku                          = var.search_sku
  local_authentication_enabled = false # enforce RBAC-only
  authentication_failure_mode  = "http401WithBearerChallenge"
  tags                         = var.tags
}
