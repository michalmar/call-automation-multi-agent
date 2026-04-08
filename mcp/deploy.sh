#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────
RESOURCE_GROUP="rg-sz"
ACA_NAME="caszmcp"
ACR_NAME="crszregistry1"
ACR_LOGIN_SERVER="crszregistry1.azurecr.io"
IMAGE_NAME="sz-mcp-server"
IMAGE_TAG="${1:-latest}"
IMAGE="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"

# Env vars for the container (no secrets – auth via managed identity)
AZURE_SEARCH_ENDPOINT="https://ais-sz-serach.search.windows.net"
AZURE_SEARCH_INDEX_NAME="sz-navestidla"
AZURE_OPENAI_ENDPOINT="https://ai-foundry-mma-eus2.openai.azure.com"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-large"
AZURE_OPENAI_API_VERSION="2025-04-01-preview"
AZURE_OPENAI_TRANSCRIPTION_MODEL="gpt-4o-transcribe-diarize"
AZURE_STORAGE_ACCOUNT_NAME="stsznahravky"
AZURE_STORAGE_INPUT_CONTAINER="input"
AZURE_STORAGE_OUTPUT_CONTAINER="output"

# ── 1. Build image in ACR ─────────────────────────────────────────────
echo "▶ Building image ${IMAGE} in ACR..."
az acr build \
  --registry "${ACR_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${IMAGE_NAME}:${IMAGE_TAG}" \
  .

# ── 2. Enable system-assigned managed identity on ACA ────────────────
echo "▶ Enabling system-assigned identity on ${ACA_NAME}..."
IDENTITY_PRINCIPAL=$(az containerapp identity assign \
  --name "${ACA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --system-assigned \
  --query principalId -o tsv 2>/dev/null || true)

if [ -z "${IDENTITY_PRINCIPAL}" ]; then
  IDENTITY_PRINCIPAL=$(az containerapp show \
    --name "${ACA_NAME}" \
    --resource-group "${RESOURCE_GROUP}" \
    --query "identity.principalId" -o tsv)
fi
echo "  Identity principal: ${IDENTITY_PRINCIPAL}"

# ── 3. Assign RBAC roles ─────────────────────────────────────────────
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

echo "▶ Assigning Cognitive Services OpenAI User role..."
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee-object-id "${IDENTITY_PRINCIPAL}" \
  --assignee-principal-type ServicePrincipal \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --only-show-errors 2>/dev/null || echo "  (already assigned or insufficient permissions)"

echo "▶ Assigning Search Index Data Reader role..."
az role assignment create \
  --role "Search Index Data Reader" \
  --assignee-object-id "${IDENTITY_PRINCIPAL}" \
  --assignee-principal-type ServicePrincipal \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --only-show-errors 2>/dev/null || echo "  (already assigned or insufficient permissions)"

echo "▶ Assigning Storage Blob Data Contributor role..."
az role assignment create \
  --role "Storage Blob Data Contributor" \
  --assignee-object-id "${IDENTITY_PRINCIPAL}" \
  --assignee-principal-type ServicePrincipal \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}" \
  --only-show-errors 2>/dev/null || echo "  (already assigned or insufficient permissions)"

# ── 4. Update Container App ──────────────────────────────────────────
echo "▶ Deploying ${IMAGE} to ${ACA_NAME}..."
az containerapp update \
  --name "${ACA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${IMAGE}" \
  --set-env-vars \
    AZURE_SEARCH_ENDPOINT="${AZURE_SEARCH_ENDPOINT}" \
    AZURE_SEARCH_INDEX_NAME="${AZURE_SEARCH_INDEX_NAME}" \
    AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT="${AZURE_OPENAI_EMBEDDING_DEPLOYMENT}" \
    AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION}" \
    AZURE_OPENAI_TRANSCRIPTION_MODEL="${AZURE_OPENAI_TRANSCRIPTION_MODEL}" \
    AZURE_STORAGE_ACCOUNT_NAME="${AZURE_STORAGE_ACCOUNT_NAME}" \
    AZURE_STORAGE_INPUT_CONTAINER="${AZURE_STORAGE_INPUT_CONTAINER}" \
    AZURE_STORAGE_OUTPUT_CONTAINER="${AZURE_STORAGE_OUTPUT_CONTAINER}"

# ── 5. Show result ───────────────────────────────────────────────────
FQDN=$(az containerapp show \
  --name "${ACA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo ""
echo "✅ Deployed successfully!"
echo "   MCP endpoint: https://${FQDN}/mcp"
