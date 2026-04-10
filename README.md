# SZ Call Analytics

Call analytics and automation platform for Czech railway infrastructure (SZ). The project includes an MCP server with vector search and audio transcription, supporting tools for data preparation, and Terraform IaC for the full Azure deployment.

## Architecture

- **MCP Server** (`mcp/`) — Model Context Protocol server deployed to Azure Container Apps. Exposes two tools:
  - `search_navestidla` — vector search over railway signalling equipment via Azure AI Search
  - `transcribe` — audio transcription from Azure Blob Storage via Azure OpenAI
- **Infrastructure** (`infra/`) — Terraform configuration for all Azure resources (ACR, AI Search, Storage, ACA, RBAC). See [infra/deployment.md](infra/deployment.md) for the full deployment guide.
- **Tools** (`tools/`) — Data preparation and ingestion utilities.

All Azure services authenticate via **managed identity** (`DefaultAzureCredential`) — no API keys.

## Quick Start

### Deploy infrastructure & application

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # edit with your values
terraform init && terraform apply               # Phase 1: provision Azure resources
./deploy.sh                                     # Phase 2: build & deploy MCP server
```

For detailed instructions, prerequisites, and architecture diagrams see **[infra/deployment.md](infra/deployment.md)**.

### Populate the search index

```bash
cd tools/aisearch_ingestion
uv sync
cp .env.example .env   # edit with your endpoints
uv run python create_index.py
uv run python ingest.py input_test2.csv
```

## Tools

### `tools/aisearch_ingestion`

Scripts to create and populate the Azure AI Search vector index from CSV data.

- `create_index.py` — creates the search index schema (vectorized `vyhledavaci_string` column, 3072-dim `text-embedding-3-large`)
- `ingest.py` — reads a `;`-delimited CSV, generates embeddings, and uploads documents in batches

See also: [tools/aisearch_ingestion/README.md](tools/aisearch_ingestion/README.md)

### `tools/SR70-view`

A small browser-based viewer for railway station data.

- Builds a searchable map and table view from SR70 station data.
- Uses Vite and Leaflet.
- Includes a data extraction script that prepares the station dataset for the frontend.

How to run:

```bash
cd tools/SR70-view
npm install
npm run dev
```

Notes:

- `npm run dev` first runs the station extraction script and then starts the Vite dev server.
- The tool expects the source workbook at `tools/SR70-view/Ciselnik.xlsx`.
- You can also build a production bundle with `npm run build`.

### `tools/transcribe-batch`

A simple batch transcription utility for WAV files.

- Transcribes audio files from an input folder.
- Writes one text transcript per source file.
- Uses an Azure OpenAI transcription deployment.

How to run:

```bash
cd tools/transcribe-batch
uv sync
cp .env.example .env
```

Set the environment variables in `.env`:

```bash
AZURE_OPENAI_ENDPOINT="https://YOUR-RESOURCE.openai.azure.com"
AZURE_OPENAI_API_KEY="YOUR_API_KEY"
AZURE_OPENAI_DEPLOYMENT_NAME="YOUR_DEPLOYMENT_NAME"
AZURE_OPENAI_API_VERSION="2025-04-01-preview"
```

Use the Azure resource URL for `AZURE_OPENAI_ENDPOINT`.
The script also accepts a value ending with `/openai/v1` and normalizes it automatically.

Then run:

```bash
uv run python transcribe_folder.py /path/to/input_wavs /path/to/output_txt
```

Optional language hint:

```bash
uv run python transcribe_folder.py /path/to/input_wavs /path/to/output_txt --language cs --temperature 0.1
```

See also: [tools/transcribe-batch/README.md](tools/transcribe-batch/README.md)

## Status

The MCP server is deployed to Azure Container Apps and consumed by Azure AI Foundry Agent Service. Infrastructure is managed via Terraform with a companion deployment script for application updates.
