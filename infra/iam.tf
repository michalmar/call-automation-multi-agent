# All RBAC role assignments for the Container App's system-assigned managed identity.

locals {
  aca_principal_id = azurerm_container_app.mcp.identity[0].principal_id
}

# ── ACR Pull (so ACA can pull images from the registry) ──────────────

resource "azurerm_role_assignment" "aca_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = local.aca_principal_id
  principal_type       = "ServicePrincipal"
}

# ── AI Search – read documents and run queries ───────────────────────

resource "azurerm_role_assignment" "aca_search_reader" {
  scope                = azurerm_search_service.main.id
  role_definition_name = "Search Index Data Reader"
  principal_id         = local.aca_principal_id
  principal_type       = "ServicePrincipal"
}

# ── Azure OpenAI – call embedding & transcription models ─────────────

resource "azurerm_role_assignment" "aca_openai_user" {
  scope                = var.openai_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = local.aca_principal_id
  principal_type       = "ServicePrincipal"
}

# ── Storage – read/write blobs (audio files & transcripts) ──────────

resource "azurerm_role_assignment" "aca_storage_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.aca_principal_id
  principal_type       = "ServicePrincipal"
}
