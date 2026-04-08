# Azure AI Search – CSV Ingestion

Ingest a semicolon-delimited CSV file into Azure AI Search. The `vyhledavaci_string` column is vectorized using **text-embedding-3-large**; all other columns (`codenov`, `m12tudu`, `obv`, `str`) are stored as filterable string fields.

## Setup

```bash
cp .env.example .env   # fill in your credentials
uv sync
```

## Usage

### 1. Create the search index

```bash
uv run python create_index.py input_test2.csv
```

This reads the CSV header to auto-generate the index schema.

### 2. Ingest documents

```bash
uv run python ingest.py input_test2.csv
```

Each CSV row becomes one search document with an auto-generated `id`, the original `vyhledavaci_string`, its vector embedding (`vyhledavaci_string_vector`), and all additional columns.
