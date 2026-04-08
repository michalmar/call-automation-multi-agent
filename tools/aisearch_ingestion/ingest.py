"""Ingest a CSV file into Azure AI Search with vector embeddings.

Each CSV row becomes one search document:
- 'vyhledavaci_string' column is embedded via text-embedding-3-large
  → stored in 'vyhledavaci_string_vector'.
- All other columns are stored as-is.
- A deterministic 'id' is generated per row (row index based).

Embeddings are requested in batches for efficiency.

Usage:
    uv run python ingest.py <csv_file>
"""

import argparse
import csv
import hashlib
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from dotenv import load_dotenv
from openai import AzureOpenAI
import os

EMBEDDING_BATCH_SIZE = 100
UPLOAD_BATCH_SIZE = 100
TEXT_COLUMN = "vyhledavaci_string"


def load_csv(csv_path: str) -> tuple[list[str], list[dict]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";", skipinitialspace=True)
        rows = list(reader)
    columns = [c.strip() for c in (reader.fieldnames or [])]
    return columns, rows


def generate_id(row_index: int, text: str) -> str:
    raw = f"{row_index}:{text}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_embeddings(client: AzureOpenAI, texts: list[str], deployment: str) -> list[list[float]]:
    response = client.embeddings.create(input=texts, model=deployment)
    return [item.embedding for item in response.data]


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Ingest CSV into Azure AI Search with embeddings.")
    parser.add_argument("csv_file", help="Path to the CSV file to ingest.")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]

    openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]
    openai_api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    columns, rows = load_csv(str(csv_path))
    if TEXT_COLUMN not in columns:
        print(f"Error: CSV must contain a '{TEXT_COLUMN}' column.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(rows)} rows from {csv_path}")

    openai_client = AzureOpenAI(
        azure_endpoint=openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=openai_api_version,
    )

    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=credential,
    )

    # Process in batches
    for batch_start in range(0, len(rows), EMBEDDING_BATCH_SIZE):
        batch_rows = rows[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
        texts = [row.get(TEXT_COLUMN, "").strip() for row in batch_rows]

        print(f"Embedding batch {batch_start // EMBEDDING_BATCH_SIZE + 1} "
              f"({len(texts)} texts)...")
        embeddings = get_embeddings(openai_client, texts, embedding_deployment)

        documents = []
        for i, (row, embedding) in enumerate(zip(batch_rows, embeddings)):
            row_index = batch_start + i
            text_value = row.get(TEXT_COLUMN, "").strip()

            doc = {
                "id": generate_id(row_index, text_value),
                TEXT_COLUMN: text_value,
                f"{TEXT_COLUMN}_vector": embedding,
            }
            for col in columns:
                if col != TEXT_COLUMN:
                    doc[col] = (row.get(col) or "").strip()

            documents.append(doc)

        # Upload batch
        for upload_start in range(0, len(documents), UPLOAD_BATCH_SIZE):
            upload_batch = documents[upload_start : upload_start + UPLOAD_BATCH_SIZE]
            result = search_client.upload_documents(documents=upload_batch)
            succeeded = sum(1 for r in result if r.succeeded)
            failed = sum(1 for r in result if not r.succeeded)
            print(f"  Uploaded {succeeded} documents, {failed} failed.")

    print("Ingestion complete.")


if __name__ == "__main__":
    main()
