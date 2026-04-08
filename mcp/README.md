# MCP Calculator Server & Agent

A simple MCP server exposing a `calc` tool (multiplication) and an agent that consumes it via the Microsoft Agent Framework.

## Setup

```bash
cd mcp
uv sync
cp .env.example .env   # then fill in your Foundry project endpoint
az login                # authenticate with Azure (Managed Identity / DefaultAzureCredential)
```

## Run

**1. Start the MCP server**

```bash
uv run server.py
```

The server listens on `http://localhost:8000/mcp` (Streamable HTTP).

**2. Run the agent** (in a second terminal)

```bash
uv run agent.py
```

## Architecture

```
agent.py ──► MCPStreamableHTTPTool ──► http://localhost:8000/mcp ──► server.py (calc tool)
```

When deployed to Azure Container Apps, point `MCP_SERVER_URL` to the container's public URL.
