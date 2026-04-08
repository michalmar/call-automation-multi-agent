"""
MCP Server with vector search over Azure AI Search.

Run locally:
    uv run server.py

The server exposes a Streamable HTTP endpoint at http://localhost:8000/mcp
"""

import json
import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import AzureOpenAI

from transcription import transcribe_from_storage

load_dotenv()

# --- Azure clients (initialised once at startup) ---

_credential = DefaultAzureCredential()

_search_client = SearchClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
    credential=_credential,
)

_openai_client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=get_bearer_token_provider(
        _credential, "https://cognitiveservices.azure.com/.default"
    ),
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
)

_embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]

# --- Transcription / Blob Storage clients ---

_transcription_model = os.environ.get(
    "AZURE_OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize"
)
_storage_account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
_input_container = os.environ.get("AZURE_STORAGE_INPUT_CONTAINER", "input")
_output_container = os.environ.get("AZURE_STORAGE_OUTPUT_CONTAINER", "output")

_blob_service: BlobServiceClient | None = None
if _storage_account:
    _blob_service = BlobServiceClient(
        account_url=f"https://{_storage_account}.blob.core.windows.net",
        credential=_credential,
    )

# --- MCP server ---

mcp = FastMCP(
    "SZ Call Analytics",
    instructions=(
        "Use search_navestidla to find railway signalling equipment. "
        "Use transcribe to transcribe audio recordings from storage."
    ),
    host="0.0.0.0",
    port=8000,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def search_navestidla(query: str) -> str:
    """Search railway signalling equipment (návěstidla) by natural-language description.

    The query is vectorized and matched against the search index.
    Returns the top 5 results with all fields (vyhledavaci_string, codenov, m12tudu, obv, str).
    """
    embedding = _openai_client.embeddings.create(
        input=[query], model=_embedding_deployment
    ).data[0].embedding

    vector_query = VectorizedQuery(
        vector=embedding,
        k_nearest_neighbors=5,
        fields="vyhledavaci_string_vector",
    )

    results = _search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["vyhledavaci_string", "codenov", "m12tudu", "obv", "str"],
        top=5,
    )

    hits = []
    for doc in results:
        hits.append({
            "vyhledavaci_string": doc["vyhledavaci_string"],
            "codenov": doc["codenov"],
            "m12tudu": doc["m12tudu"],
            "obv": doc["obv"],
            "str": doc["str"],
            "score": doc["@search.score"],
        })

    return json.dumps(hits, ensure_ascii=False, indent=2)


@mcp.tool()
def transcribe(filename: str) -> str:
    """Transcribe an audio file from Azure Blob Storage.

    Downloads the file from the input container, transcribes it using
    Azure OpenAI (gpt-4o-transcribe-diarize with speaker diarization),
    and uploads the transcript to the output container.

    Args:
        filename: Name of the audio file in the input container (e.g. "98289.wav").

    Returns:
        The full transcript text with timestamps and speaker labels.
    """
    if _blob_service is None:
        return "Error: AZURE_STORAGE_ACCOUNT_NAME is not configured."

    return transcribe_from_storage(
        openai_client=_openai_client,
        blob_service=_blob_service,
        input_container=_input_container,
        output_container=_output_container,
        filename=filename,
        model=_transcription_model,
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
