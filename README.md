# SZ Call Analytics

This repository is intended for call analytics and automation work.

At the moment, the project mostly contains helper tools collected under [tools/SR70-view](tools/SR70-view) and [tools/transcribe-batch](tools/transcribe-batch).

## Tools

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

The main call analytics pipeline is not here yet. Right now this repository serves as a place for supporting utilities that help with data preparation, inspection, and transcription.
