# Azure WAV folder transcription

Setup:

```bash
uv sync
```

Create `.env` from `.env.example` and fill in the values:

```bash
cp .env.example .env
```

Environment variables:

```bash
AZURE_OPENAI_ENDPOINT="https://YOUR-RESOURCE.openai.azure.com"
AZURE_OPENAI_API_KEY="YOUR_API_KEY"
AZURE_OPENAI_DEPLOYMENT_NAME="YOUR_DEPLOYMENT_NAME"
AZURE_OPENAI_API_VERSION="2025-04-01-preview"
AZURE_OPENAI_TEMPERATURE="0"
```

Use the Azure resource URL for `AZURE_OPENAI_ENDPOINT`.
The script also accepts a value ending with `/openai/v1` and normalizes it automatically.

`AZURE_OPENAI_DEPLOYMENT_NAME` must be your Azure deployment name.

Run:

```bash
uv run python transcribe_folder.py /path/to/input_wavs /path/to/output_txt
```

Optional language hint:

```bash
uv run python transcribe_folder.py /path/to/input_wavs /path/to/output_txt --language cs
```

Optional temperature control:

```bash
uv run python transcribe_folder.py /path/to/input_wavs /path/to/output_txt --temperature 0.2
```

`temperature` is supported by the SDK for transcription requests, including
`gpt-4o-transcribe-diarize`. Valid values are from `0` to `1`. Lower values are
more deterministic; `0` lets the model auto-increase temperature from log-probability
thresholds when needed.

The console output now also shows how long each transcription request took and the
overall elapsed time for the whole batch run. Transcript `.txt` files still contain
only transcript text.
