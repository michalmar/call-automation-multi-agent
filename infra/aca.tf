# ── Log Analytics (required by ACA Environment) ──────────────────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${var.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

# ── Container App Environment ────────────────────────────────────────

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.prefix}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

# ── Container App ────────────────────────────────────────────────────

resource "azurerm_container_app" "mcp" {
  name                         = "ca-${var.prefix}-mcp"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = "System"
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # Initial hello-world container — replaced by deploy.sh after first apply
  template {
    min_replicas = var.aca_min_replicas
    max_replicas = var.aca_max_replicas

    container {
      name   = "mcp-server"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = var.aca_cpu
      memory = var.aca_memory

      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = "https://${azurerm_search_service.main.name}.search.windows.net"
      }
      env {
        name  = "AZURE_SEARCH_INDEX_NAME"
        value = "sz-navestidla"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = var.openai_embedding_deployment
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = var.openai_api_version
      }
      env {
        name  = "AZURE_OPENAI_TRANSCRIPTION_MODEL"
        value = var.openai_transcription_model
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.main.name
      }
      env {
        name  = "AZURE_STORAGE_INPUT_CONTAINER"
        value = azurerm_storage_container.input.name
      }
      env {
        name  = "AZURE_STORAGE_OUTPUT_CONTAINER"
        value = azurerm_storage_container.output.name
      }
    }
  }
}
