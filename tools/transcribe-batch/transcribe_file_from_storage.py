#!/usr/bin/env python3
"""Transcribe a single WAV file from Azure Blob Storage.

Downloads the file from an input container, transcribes it with
Azure OpenAI, and uploads the transcript to an output container.

Required environment variables:
    AZURE_OPENAI_ENDPOINT
    AZURE_STORAGE_ACCOUNT_NAME
    AZURE_STORAGE_INPUT_CONTAINER
    AZURE_STORAGE_OUTPUT_CONTAINER

Optional environment variables:
    AZURE_OPENAI_API_KEY               Falls back to Entra ID (DefaultAzureCredential)
    AZURE_OPENAI_TRANSCRIPTION_MODEL   Defaults to gpt-4o-transcribe-diarize
    AZURE_OPENAI_API_VERSION           Defaults to 2025-04-01-preview
    AZURE_OPENAI_TEMPERATURE           Optional float from 0 to 1

Example:
    python3 transcribe_file_from_storage.py 98289.wav
"""

from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from openai import APIStatusError, AzureOpenAI


DEFAULT_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_API_VERSION = "2025-04-01-preview"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download a .wav file from Azure Blob Storage, transcribe it, "
            "and upload the transcript back to a different container."
        )
    )
    parser.add_argument(
        "input_filename",
        help="Name of the .wav file in the input container (e.g. 98289.wav).",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Optional ISO-639-1 language hint such as en or cs.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature from 0 to 1.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Settings helpers (reused from transcribe_folder.py)
# ---------------------------------------------------------------------------

def get_required_env(env_name: str) -> str:
    value = os.getenv(env_name)
    if value:
        return value
    raise SystemExit(f"Missing required environment variable: {env_name}")


def get_optional_env(env_name: str, default: str) -> str:
    return os.getenv(env_name, default)


def get_optional_env_from_names(env_names: tuple[str, ...], default: str) -> str:
    for name in env_names:
        value = os.getenv(name)
        if value:
            return value
    return default


def get_optional_float_env(env_name: str) -> float | None:
    value = os.getenv(env_name)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid float for {env_name}: {value}") from exc


def validate_temperature(temperature: float | None) -> float | None:
    if temperature is None:
        return None
    if 0 <= temperature <= 1:
        return temperature
    raise SystemExit("Temperature must be between 0 and 1.")


# ---------------------------------------------------------------------------
# Azure OpenAI helpers (reused from transcribe_folder.py)
# ---------------------------------------------------------------------------

def normalize_endpoint(endpoint: str) -> str:
    trimmed = endpoint.rstrip("/")
    if trimmed.endswith("/openai/v1"):
        return trimmed[: -len("/openai/v1")]
    return trimmed


def normalize_api_version(api_version: str) -> str:
    if api_version == "preview":
        return DEFAULT_API_VERSION
    return api_version


def build_openai_client(
    endpoint: str,
    api_key: str | None,
    api_version: str,
    credential: DefaultAzureCredential | None = None,
) -> AzureOpenAI:
    normalized = normalize_endpoint(endpoint)
    version = normalize_api_version(api_version)

    if api_key:
        return AzureOpenAI(
            api_key=api_key,
            azure_endpoint=normalized,
            api_version=version,
        )

    # Token-based auth via DefaultAzureCredential
    if credential is None:
        credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_ad_token_provider=token_provider,
        azure_endpoint=normalized,
        api_version=version,
    )


# ---------------------------------------------------------------------------
# Transcript formatting (reused from transcribe_folder.py)
# ---------------------------------------------------------------------------

def to_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()
        if isinstance(dumped, dict):
            return dumped
    raise TypeError("Unexpected transcription response type.")


def format_timestamp(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "?"
    total = max(0, int(round(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration(seconds: float) -> str:
    return f"{seconds:.2f}s"


def format_transcript(result: Any) -> str:
    payload = to_mapping(result)
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
            start = format_timestamp(segment.get("start"))
            end = format_timestamp(segment.get("end"))
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
# Transcription
# ---------------------------------------------------------------------------

def transcribe_file(
    client: AzureOpenAI,
    audio_path: Path,
    model: str,
    language: str | None,
    temperature: float | None,
) -> tuple[str, float]:
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
                raise SystemExit(
                    "Azure deployment not found. Check "
                    "AZURE_OPENAI_DEPLOYMENT_NAME / AZURE_OPENAI_TRANSCRIPTION_MODEL."
                ) from exc
            if exc.status_code == 400 and "chunking_strategy is required" in str(exc):
                raise SystemExit(
                    "chunking_strategy is required for diarization models."
                ) from exc
            raise

    return format_transcript(result), elapsed


# ---------------------------------------------------------------------------
# Azure Blob Storage helpers
# ---------------------------------------------------------------------------

def build_blob_service_client(account_name: str) -> BlobServiceClient:
    account_url = f"https://{account_name}.blob.core.windows.net"
    credential = DefaultAzureCredential()
    return BlobServiceClient(account_url=account_url, credential=credential)


def download_blob_to_tempfile(
    blob_service: BlobServiceClient,
    container: str,
    blob_name: str,
) -> Path:
    """Download a blob into a temporary file and return its path."""
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
    blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
    blob_client.upload_blob(text.encode("utf-8"), overwrite=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()
    args = parse_args()

    # Azure OpenAI settings
    endpoint = get_required_env("AZURE_OPENAI_ENDPOINT")
    model = get_optional_env_from_names(
        ("AZURE_OPENAI_DEPLOYMENT_NAME", "AZURE_OPENAI_TRANSCRIPTION_MODEL"),
        DEFAULT_MODEL,
    )
    api_version = get_optional_env("AZURE_OPENAI_API_VERSION", DEFAULT_API_VERSION)
    temperature = validate_temperature(
        args.temperature
        if args.temperature is not None
        else get_optional_float_env("AZURE_OPENAI_TEMPERATURE")
    )

    # Azure Storage settings
    account_name = get_required_env("AZURE_STORAGE_ACCOUNT_NAME")
    input_container = get_required_env("AZURE_STORAGE_INPUT_CONTAINER")
    output_container = get_required_env("AZURE_STORAGE_OUTPUT_CONTAINER")

    input_filename = args.input_filename
    output_filename = Path(input_filename).stem + ".txt"

    # Build clients – share credential for both Storage and OpenAI (Entra ID)
    credential = DefaultAzureCredential()
    openai_client = build_openai_client(endpoint, None, api_version, credential)
    blob_service = build_blob_service_client(account_name)

    # Download
    print(f"Downloading {input_filename} from container '{input_container}'...")
    tmp_path = download_blob_to_tempfile(blob_service, input_container, input_filename)

    try:
        # Transcribe
        print(f"Transcribing {input_filename}...")
        transcript, elapsed = transcribe_file(
            client=openai_client,
            audio_path=tmp_path,
            model=model,
            language=args.language,
            temperature=temperature,
        )
        print(f"Transcription completed in {format_duration(elapsed)}.")

        # Upload
        print(f"Uploading {output_filename} to container '{output_container}'...")
        upload_text_to_blob(blob_service, output_container, output_filename, transcript + "\n")
        print("Done.")
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
