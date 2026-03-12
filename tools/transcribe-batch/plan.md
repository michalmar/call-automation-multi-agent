Problem: Create a simple Python CLI that transcribes WAV files from an input folder using an existing Azure AI Foundry deployment of the `gpt-4o-transcribe-diarize` model, then writes one `.txt` transcript per source file into an output folder.

Approach:
- Use the official `openai` Python SDK against the Azure OpenAI-compatible `/openai/v1/` endpoint.
- Default to the latest preview transcription API by sending `api-version=preview`.
- Read all `.wav` files from an input folder, transcribe them one by one, and write matching `.txt` files to the output folder.
- Preserve speaker labels in output when the diarization response includes per-segment speaker metadata.

Todos:
- research-api: verify the current Azure/OpenAI transcription API usage for `gpt-4o-transcribe-diarize`.
- write-script: implement the CLI and folder processing flow.
- document-usage: provide dependency and run instructions in the repository.

Notes:
- Configuration is environment-based to avoid hardcoding secrets.
- The script accepts an explicit model/deployment name override in case the Azure deployment name differs from `gpt-4o-transcribe-diarize`.
