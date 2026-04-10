# ── General ───────────────────────────────────────────────────────────

variable "subscription_id" {
  description = "Azure subscription ID."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group to create."
  type        = string
  default     = "rg-sz"
}

variable "location" {
  description = "Azure region for all resources."
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    project = "sz-call-analytics"
  }
}

# ── Naming prefix ────────────────────────────────────────────────────

variable "prefix" {
  description = "Short prefix used for globally unique resource names."
  type        = string
  default     = "sz"
}

# ── Container Registry ───────────────────────────────────────────────

variable "acr_sku" {
  description = "SKU for Azure Container Registry."
  type        = string
  default     = "Basic"
}

# ── AI Search ────────────────────────────────────────────────────────

variable "search_sku" {
  description = "SKU for Azure AI Search."
  type        = string
  default     = "basic"
}

# ── Storage ──────────────────────────────────────────────────────────

variable "storage_sku" {
  description = "Replication SKU for the storage account."
  type        = string
  default     = "Standard_LRS"
}

# ── Container App ────────────────────────────────────────────────────

variable "aca_cpu" {
  description = "CPU cores for the container app."
  type        = number
  default     = 0.5
}

variable "aca_memory" {
  description = "Memory (Gi) for the container app."
  type        = string
  default     = "1Gi"
}

variable "aca_min_replicas" {
  description = "Minimum number of ACA replicas."
  type        = number
  default     = 0
}

variable "aca_max_replicas" {
  description = "Maximum number of ACA replicas."
  type        = number
  default     = 3
}

# ── External Azure OpenAI resource (not managed by this Terraform) ──

variable "openai_resource_id" {
  description = "Full resource ID of the existing Azure OpenAI / AI Services account (for RBAC assignment)."
  type        = string
}

variable "openai_endpoint" {
  description = "Azure OpenAI endpoint URL (e.g. https://myresource.openai.azure.com)."
  type        = string
}

variable "openai_embedding_deployment" {
  description = "Deployment name for the embedding model."
  type        = string
  default     = "text-embedding-3-large"
}

variable "openai_transcription_model" {
  description = "Deployment name for the transcription model."
  type        = string
  default     = "gpt-4o-transcribe-diarize"
}

variable "openai_api_version" {
  description = "Azure OpenAI API version."
  type        = string
  default     = "2025-04-01-preview"
}
