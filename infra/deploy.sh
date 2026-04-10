#!/usr/bin/env bash
# deploy.sh — Build the MCP server image in ACR and deploy to ACA.
#
# Prerequisites:
#   1. Terraform has been applied (infra exists).
#   2. You are logged in: az login
#
# Usage:
#   ./deploy.sh              # uses "latest" tag
#   ./deploy.sh v1.2.3       # uses custom tag
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$(cd "${SCRIPT_DIR}/../mcp" && pwd)"

IMAGE_TAG="${1:-latest}"

# ── Read Terraform outputs ───────────────────────────────────────────
echo "▶ Reading Terraform outputs..."
RESOURCE_GROUP=$(terraform -chdir="${SCRIPT_DIR}" output -raw resource_group_name)
ACR_NAME=$(terraform -chdir="${SCRIPT_DIR}" output -raw acr_name)
ACR_LOGIN_SERVER=$(terraform -chdir="${SCRIPT_DIR}" output -raw acr_login_server)
ACA_NAME=$(terraform -chdir="${SCRIPT_DIR}" output -raw aca_name)

IMAGE="${ACR_LOGIN_SERVER}/sz-mcp-server:${IMAGE_TAG}"

echo "  Resource Group : ${RESOURCE_GROUP}"
echo "  ACR            : ${ACR_LOGIN_SERVER}"
echo "  ACA            : ${ACA_NAME}"
echo "  Image          : ${IMAGE}"
echo ""

# ── 1. Build image in ACR ────────────────────────────────────────────
echo "▶ Building image in ACR (cloud build)..."
az acr build \
  --registry "${ACR_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "sz-mcp-server:${IMAGE_TAG}" \
  "${MCP_DIR}"

# ── 2. Update Container App image ────────────────────────────────────
echo "▶ Updating Container App with new image..."
az containerapp update \
  --name "${ACA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${IMAGE}" \
  -o none

# ── 3. Verify ────────────────────────────────────────────────────────
MCP_ENDPOINT=$(terraform -chdir="${SCRIPT_DIR}" output -raw mcp_endpoint)

echo ""
echo "▶ Verifying deployment..."
HTTP_CODE=$(curl -s --max-time 30 -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"deploy-check","version":"1.0"}},"id":1}' \
  "${MCP_ENDPOINT}" 2>/dev/null || echo "000")

if [ "${HTTP_CODE}" = "200" ]; then
  echo "✅ Deployment successful!"
else
  echo "⚠️  MCP endpoint returned HTTP ${HTTP_CODE} (may need a minute to start)."
fi

echo "   MCP endpoint: ${MCP_ENDPOINT}"
