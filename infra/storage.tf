resource "azurerm_storage_account" "main" {
  name                     = "st${var.prefix}nahravky"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = var.storage_sku
  account_kind             = "StorageV2"

  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

resource "azurerm_storage_container" "input" {
  name                  = "input"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "output" {
  name                  = "output"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}
