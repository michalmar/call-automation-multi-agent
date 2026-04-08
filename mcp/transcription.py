"""Transcription utilities for Azure Blob Storage + Azure OpenAI.

Downloads a WAV file from a storage container, transcribes it with
Azure OpenAI (gpt-4o-transcribe-diarize), and uploads the result as
a .txt file to an output container.

All Azure authentication goes through DefaultAzureCredential.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from azure.storage.blob import BlobServiceClient
from openai import APIStatusError, AzureOpenAI

DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe-diarize"


# ---------------------------------------------------------------------------
# Transcript formatting
# ---------------------------------------------------------------------------

def _to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    raise TypeError("Unexpected transcription response type.")


def _format_timestamp(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "?"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_transcript(result: Any) -> str:
    """Turn an OpenAI transcription response into readable text."""
    payload = _to_mapping(result)
    segments = payload.get("segments")

    if isinstance(segments, list) and segments:
        lines: list[str] = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text", "")).strip()
            if not text:
                continue
            speaker = (
                segment.get("speaker")
                or segment.get("speaker_id")
                or segment.get("speaker_label")
            )
            start = _format_timestamp(segment.get("start"))
            end = _format_timestamp(segment.get("end"))
            if speaker is not None:
                lines.append(f"[{start} - {end}] Speaker {speaker}: {text}")
            else:
                lines.append(f"[{start} - {end}] {text}")
        if lines:
            return "\n".join(lines)

    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    raise ValueError("Transcription response did not contain transcript text.")


# ---------------------------------------------------------------------------
# Azure Blob Storage helpers
# ---------------------------------------------------------------------------

def download_blob_to_tempfile(
    blob_service: BlobServiceClient,
    container: str,
    blob_name: str,
) -> Path:
    """Download a blob to a temporary file and return its path."""
    blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
    suffix = Path(blob_name).suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        stream = blob_client.download_blob()
        stream.readinto(tmp)
        tmp.close()
    except Exception:
        tmp.close()
        Path(tmp.name).unlink(missing_ok=True)
        raise
    return Path(tmp.name)


def upload_text_to_blob(
    blob_service: BlobServiceClient,
    container: str,
    blob_name: str,
    text: str,
) -> None:
    """Upload UTF-8 text as a blob, overwriting if it already exists."""
    blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
    blob_client.upload_blob(text.encode("utf-8"), overwrite=True)


# ---------------------------------------------------------------------------
# Core transcription
# ---------------------------------------------------------------------------

def transcribe_audio(
    client: AzureOpenAI,
    audio_path: Path,
    model: str = DEFAULT_TRANSCRIPTION_MODEL,
    language: str | None = None,
    temperature: float | None = None,
) -> tuple[str, float]:
    """Transcribe a local audio file and return (transcript_text, elapsed_seconds)."""
    request: dict[str, Any] = {
        "file": audio_path.open("rb"),
        "model": model,
        "response_format": "diarized_json" if "diarize" in model else "json",
    }
    if "diarize" in model:
        request["chunking_strategy"] = "auto"
    if language:
        request["language"] = language
    if temperature is not None:
        request["temperature"] = temperature

    with request["file"]:
        try:
            started_at = time.perf_counter()
            result = client.audio.transcriptions.create(**request)
            elapsed = time.perf_counter() - started_at
        except APIStatusError as exc:
            if exc.status_code == 404 and "DeploymentNotFound" in str(exc):
                raise RuntimeError(
                    f"Deployment '{model}' not found. Check "
                    "AZURE_OPENAI_TRANSCRIPTION_MODEL."
                ) from exc
            raise

    return format_transcript(result), elapsed


# ---------------------------------------------------------------------------
# High-level: storage → transcribe → storage
# ---------------------------------------------------------------------------

def transcribe_from_storage(
    openai_client: AzureOpenAI,
    blob_service: BlobServiceClient,
    input_container: str,
    output_container: str,
    filename: str,
    model: str = DEFAULT_TRANSCRIPTION_MODEL,
    language: str | None = None,
    temperature: float | None = None,
) -> str:
    """Download *filename* from storage, transcribe, upload result, return text."""
    output_name = Path(filename).stem + ".txt"
    tmp_path = download_blob_to_tempfile(blob_service, input_container, filename)

    try:
        transcript, elapsed = transcribe_audio(
            client=openai_client,
            audio_path=tmp_path,
            model=model,
            language=language,
            temperature=temperature,
        )
        upload_text_to_blob(blob_service, output_container, output_name, transcript + "\n")
    finally:
        tmp_path.unlink(missing_ok=True)

    return transcript
