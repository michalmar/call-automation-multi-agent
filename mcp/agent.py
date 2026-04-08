"""
Agent that uses the MCP server to search railway signalling equipment.

Prerequisites:
  1. Start the MCP server:  uv run server.py
  2. Log in to Azure:  az login
  3. Set environment variables (or use .env file):
       FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
  4. Run the agent:  uv run agent.py
"""

import asyncio
import os

from dotenv import load_dotenv

from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")


async def main() -> None:
    credential = DefaultAzureCredential()

    client = FoundryChatClient(
        credential=credential,
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        model=os.getenv("FOUNDRY_MODEL", "gpt-5-mini"),
    )

    mcp_tool = MCPStreamableHTTPTool(
        name="search",
        url=MCP_SERVER_URL,
        description="Search railway signalling equipment (návěstidla) by description.",
    )

    INSTRUCTIONS = (
                "You are a railway signalling analyst for Czech Railways (SŽDC).\n"
                "\n"
                "## Workflow\n"
                "When the user asks you to process a recording:\n"
                "1. **Transcribe** – call the `transcribe` tool with the given filename.\n"
                "2. **Extract identifiers** – from the transcript, identify every mention of\n"
                "   a railway signalling device (návěstidlo). Look for patterns like a code\n"
                "   (e.g. '1L', 'S1', 'Se2', 'PřSe3') together with a station or location\n"
                "   name (e.g. 'Tlumačov', 'Otrokovice').\n"
                "3. **Search** – for each identified device, call `search_navestidla` with a\n"
                "   query combining the device code and station name\n"
                "   (e.g. 'návěstidlo 1L stanice Tlumačov').\n"
                "4. **Report results**:\n"
                "   - If one result clearly matches, output its full metadata\n"
                "     (codenov, m12tudu, obv, str, vyhledavaci_string).\n"
                "   - If the match is ambiguous, list the top 3 candidates with their\n"
                "     metadata and note the uncertainty.\n"
                "   - If nothing relevant is found, say so explicitly.\n"
                "\n"
                "## Guidelines\n"
                "- The search is semantic (vector-based), so craft queries in natural Czech\n"
                "  using the terminology from the transcript.\n"
                "- Always include both the device code AND the station/location in the query.\n"
                "- Process all signalling devices mentioned in the recording, not just the first one.\n"
                "- Present the final output in a clear, structured format (table or list).\n"
                "- If the user asks a direct search question (without a recording), skip\n"
                "  transcription and go straight to step 3.\n"
            )
    print("Agent instructions:")
    print(INSTRUCTIONS)

    async with mcp_tool:
        agent = Agent(
            client=client,
            name="SearchAgent",
            instructions=INSTRUCTIONS,
            tools=mcp_tool,
        )

        
        result = await agent.run("Analyzuj 982289.wav a najdi všechny návěstidla, která jsou v nahrávce zmíněna.")
        print(f"Agent: {result}")

    await credential.close()


if __name__ == "__main__":
    asyncio.run(main())
