#Requires -Version 7.0
<#
.SYNOPSIS
    Build and deploy the SZ MCP server to Azure Container Apps.
.PARAMETER ImageTag
    Docker image tag (default: "latest").
.EXAMPLE
    ./deploy.ps1
    ./deploy.ps1 -ImageTag "v2"
#>
param(
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# ── Configuration ────────────────────────────────────────────────────
$ResourceGroup              = "rg-sz"
$AcaName                    = "caszmcp"
$AcrName                    = "crszregistry1"
$AcrLoginServer             = "crszregistry1.azurecr.io"
$ImageName                  = "sz-mcp-server"
$Image                      = "$AcrLoginServer/${ImageName}:$ImageTag"

# Env vars for the container (no secrets – auth via managed identity)
$EnvVars = @{
    AZURE_SEARCH_ENDPOINT              = "https://ais-sz-serach.search.windows.net"
    AZURE_SEARCH_INDEX_NAME            = "sz-navestidla"
    AZURE_OPENAI_ENDPOINT              = "https://ai-foundry-mma-eus2.openai.azure.com"
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT  = "text-embedding-3-large"
    AZURE_OPENAI_API_VERSION           = "2025-04-01-preview"
    AZURE_OPENAI_TRANSCRIPTION_MODEL   = "gpt-4o-transcribe-diarize"
    AZURE_STORAGE_ACCOUNT_NAME         = "stsznahravky"
    AZURE_STORAGE_INPUT_CONTAINER      = "input"
    AZURE_STORAGE_OUTPUT_CONTAINER     = "output"
}

# ── 1. Build image in ACR ─────────────────────────────────────────────
Write-Host "▶ Building image $Image in ACR..."
az acr build `
    --registry $AcrName `
    --resource-group $ResourceGroup `
    --image "${ImageName}:$ImageTag" `
    .
if ($LASTEXITCODE -ne 0) { throw "ACR build failed." }

# ── 2. Enable system-assigned managed identity on ACA ────────────────
Write-Host "▶ Enabling system-assigned identity on $AcaName..."
$IdentityPrincipal = az containerapp identity assign `
    --name $AcaName `
    --resource-group $ResourceGroup `
    --system-assigned `
    --query principalId -o tsv 2>$null

if (-not $IdentityPrincipal) {
    $IdentityPrincipal = az containerapp show `
        --name $AcaName `
        --resource-group $ResourceGroup `
        --query "identity.principalId" -o tsv
}
Write-Host "  Identity principal: $IdentityPrincipal"

# ── 3. Assign RBAC roles ─────────────────────────────────────────────
$SubscriptionId = az account show --query id -o tsv
$Scope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"

$Roles = @(
    "Cognitive Services OpenAI User",
    "Search Index Data Reader",
    "Storage Blob Data Contributor"
)

foreach ($Role in $Roles) {
    Write-Host "▶ Assigning $Role role..."
    az role assignment create `
        --role $Role `
        --assignee-object-id $IdentityPrincipal `
        --assignee-principal-type ServicePrincipal `
        --scope $Scope `
        --only-show-errors 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (already assigned or insufficient permissions)"
    }
}

# ── 4. Update Container App ──────────────────────────────────────────
Write-Host "▶ Deploying $Image to $AcaName..."
$SetEnvVars = ($EnvVars.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" })

az containerapp update `
    --name $AcaName `
    --resource-group $ResourceGroup `
    --image $Image `
    --set-env-vars @SetEnvVars
if ($LASTEXITCODE -ne 0) { throw "Container App update failed." }

# ── 5. Show result ───────────────────────────────────────────────────
$Fqdn = az containerapp show `
    --name $AcaName `
    --resource-group $ResourceGroup `
    --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host ""
Write-Host "✅ Deployed successfully!"
Write-Host "   MCP endpoint: https://$Fqdn/mcp"
