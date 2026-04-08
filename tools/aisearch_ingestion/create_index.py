"""Create an Azure AI Search index from a CSV file.

Reads the CSV header to build the index schema automatically:
- The 'vyhledavaci_string' column becomes a searchable text field
  + a vector field (vyhledavaci_string_vector).
- All other columns become filterable/searchable string fields.
- A synthetic 'id' field is added as the document key.

Usage:
    uv run python create_index.py <csv_file>
"""

import argparse
import csv
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from dotenv import load_dotenv
import os

VECTOR_DIMENSIONS = 3072  # text-embedding-3-large
TEXT_COLUMN = "vyhledavaci_string"


def read_csv_columns(csv_path: str) -> list[str]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
    return [h.strip() for h in headers]


def build_index(index_name: str, extra_columns: list[str]) -> SearchIndex:
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name=TEXT_COLUMN,
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SearchField(
            name=f"{TEXT_COLUMN}_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMENSIONS,
            vector_search_profile_name="default-vector-profile",
        ),
    ]

    for col in extra_columns:
        fields.append(
            SimpleField(
                name=col,
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True,
            )
        )

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="default-vector-profile",
                algorithm_configuration_name="default-hnsw",
            )
        ],
    )

    return SearchIndex(name=index_name, fields=fields, vector_search=vector_search)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Create Azure AI Search index from CSV schema.")
    parser.add_argument("csv_file", help="Path to the CSV file whose header defines the schema.")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    credential = DefaultAzureCredential()

    columns = read_csv_columns(str(csv_path))
    if TEXT_COLUMN not in columns:
        print(f"Error: CSV must contain a '{TEXT_COLUMN}' column.", file=sys.stderr)
        sys.exit(1)

    extra_columns = [c for c in columns if c != TEXT_COLUMN]
    print(f"CSV columns: {columns}")
    print(f"Extra columns (non-vectorized): {extra_columns}")

    index = build_index(index_name, extra_columns)

    client = SearchIndexClient(endpoint=endpoint, credential=credential)
    result = client.create_or_update_index(index)
    print(f"Index '{result.name}' created/updated successfully.")


if __name__ == "__main__":
    main()
