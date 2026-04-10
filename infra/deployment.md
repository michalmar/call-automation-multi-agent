# Deployment Guide

This project uses a **two-phase deployment** model:

1. **Phase 1 — Infrastructure** (`terraform apply`): provisions all Azure resources with a placeholder container image.
2. **Phase 2 — Application** (`deploy.sh`): builds the MCP server image in ACR and updates the Container App.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Resource Group (rg-sz)                                  │
│                                                          │
│  ┌──────────────┐   ┌──────────────┐  ┌──────────────┐  │
│  │ Container    │   │ AI Search    │  │ Storage      │  │
│  │ Registry     │   │              │  │ Account      │  │
│  │ (ACR)        │   │ RBAC-only    │  │ input/output │  │
│  └──────┬───────┘   └──────┬───────┘  └──────┬───────┘  │
│         │ AcrPull          │ Reader          │ Blob     │
│         ▼                  ▼                 ▼          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Container App (MCP Server)                      │    │
│  │ System-Assigned Managed Identity                │    │
│  │ Port 8000 · External Ingress                    │    │
│  └─────────────────────────┬───────────────────────┘    │
│                             │ OpenAI User               │
└─────────────────────────────┼────────────────────────────┘
                              ▼
                ┌──────────────────────────┐
                │ Azure OpenAI / AI Foundry│
                │ (external resource)      │
                └──────────────────────────┘
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) ≥ 1.5
- Azure CLI (`az login` completed)
- Sufficient permissions: Contributor + User Access Administrator on the subscription

## Phase 1 — Provision Infrastructure

```bash
cd infra

# First time only
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

This creates:

| Resource | Purpose |
|---|---|
| Resource Group | Contains all project resources |
| Container Registry | Hosts MCP server Docker images |
| AI Search | Vector search index for railway equipment |
| Storage Account | Blob containers for audio files (input/output) |
| Log Analytics Workspace | Logging for ACA environment |
| Container App Environment | Hosting environment for the container app |
| Container App | Runs MCP server (starts with hello-world image) |
| RBAC Assignments | AcrPull, Search Reader, OpenAI User, Storage Blob Contributor |

The Container App is created with a **placeholder image** (`mcr.microsoft.com/k8se/quickstart:latest`).
All environment variables are pre-configured.

## Phase 2 — Deploy Application

After infrastructure is provisioned, deploy the actual MCP server:

```bash
cd infra
./deploy.sh          # builds & deploys with "latest" tag
./deploy.sh v1.0.0   # or use a specific tag
```

The script:
1. Reads resource names from Terraform outputs (no hardcoded values)
2. Builds the Docker image inside ACR (`az acr build`, no local Docker needed)
3. Updates the Container App with the new image
4. Verifies the MCP endpoint responds

## Updating the Application

After code changes to `mcp/server.py`, simply re-run:

```bash
cd infra && ./deploy.sh
```

No `terraform apply` needed — infrastructure stays unchanged.

## Updating Infrastructure

If you add new resources or change configuration:

```bash
cd infra
terraform plan -out=tfplan
terraform apply tfplan
```

> **Note:** Terraform manages env vars on the Container App. If you change env vars
> via `az containerapp update` outside Terraform, the next `terraform apply` will
> revert them. Always update env vars in `aca.tf`.

## Resource Naming Convention

| Resource Type | Naming Pattern | Example |
|---|---|---|
| Resource Group | `rg-{prefix}` | `rg-sz` |
| Container Registry | `cr{prefix}registry` | `crszregistry` |
| AI Search | `ais-{prefix}-search` | `ais-sz-search` |
| Storage Account | `st{prefix}nahravky` | `stsznahravky` |
| Log Analytics | `law-{prefix}` | `law-sz` |
| ACA Environment | `cae-{prefix}` | `cae-sz` |
| Container App | `ca-{prefix}-mcp` | `ca-sz-mcp` |

## Security

- **No API keys** — all services authenticate via `DefaultAzureCredential` (system-assigned managed identity).
- **RBAC-only** on AI Search (`local_authentication_enabled = false`).
- **ACR admin disabled** — image pull uses managed identity.
- The Azure OpenAI resource is external and referenced by resource ID for RBAC assignment only.
