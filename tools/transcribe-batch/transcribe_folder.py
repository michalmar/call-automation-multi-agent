#!/usr/bin/env python3
"""Transcribe all WAV files in a folder with Azure AI Foundry / Azure OpenAI.

Required environment variables:
    AZURE_OPENAI_ENDPOINT             Accepts either the resource URL or the
                                                                     same URL with /openai/v1 appended.
  AZURE_OPENAI_API_KEY

Optional environment variables:
  AZURE_OPENAI_TRANSCRIPTION_MODEL   Defaults to gpt-4o-transcribe-diarize
  AZURE_OPENAI_API_VERSION           Defaults to preview
    AZURE_OPENAI_TEMPERATURE           Optional float from 0 to 1

Example:
  python3 transcribe_folder.py ./input_wavs ./transcripts
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time
from typing import Any

from openai import APIStatusError, AzureOpenAI
from dotenv import load_dotenv


DEFAULT_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_API_VERSION = "2025-04-01-preview"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Transcribe all .wav files from an input folder and write one .txt "
            "transcript per file into the output folder."
        )
    )
    parser.add_argument("input_dir", type=Path, help="Folder containing .wav files.")
    parser.add_argument("output_dir", type=Path, help="Folder for transcript .txt files.")
    parser.add_argument(
        "--endpoint",
        default=None,
        help=(
            "Azure OpenAI endpoint. Accepts either the resource URL or the "
            "same URL with /openai/v1. Falls back to AZURE_OPENAI_ENDPOINT."
        ),
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Azure OpenAI API key. Falls back to AZURE_OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Azure deployment name. Falls back to AZURE_OPENAI_DEPLOYMENT_NAME, "
            "AZURE_OPENAI_TRANSCRIPTION_MODEL, or gpt-4o-transcribe-diarize."
        ),
    )
    parser.add_argument(
        "--api-version",
        default=None,
        help=(
            "Azure OpenAI API version query value. Falls back to "
            "AZURE_OPENAI_API_VERSION or preview."
        ),
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
        help=(
            "Optional sampling temperature from 0 to 1. Falls back to "
            "AZURE_OPENAI_TEMPERATURE. Lower values are more deterministic."
        ),
    )
    return parser.parse_args()


def get_required_setting(cli_value: str | None, env_name: str) -> str:
    if cli_value:
        return cli_value

    import os

    env_value = os.getenv(env_name)
    if env_value:
        return env_value

    raise SystemExit(f"Missing required setting: {env_name}")


def get_optional_setting(cli_value: str | None, env_name: str, default: str) -> str:
    if cli_value:
        return cli_value

    import os

    return os.getenv(env_name, default)


def get_optional_setting_from_names(
    cli_value: str | None,
    env_names: tuple[str, ...],
    default: str,
) -> str:
    if cli_value:
        return cli_value

    import os

    for env_name in env_names:
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
    return default


def get_optional_float_setting(cli_value: float | None, env_name: str) -> float | None:
    if cli_value is not None:
        return cli_value

    import os

    env_value = os.getenv(env_name)
    if env_value is None or not env_value.strip():
        return None

    try:
        return float(env_value)
    except ValueError as exc:
        raise SystemExit(f"Invalid float value for {env_name}: {env_value}") from exc


def validate_temperature(temperature: float | None) -> float | None:
    if temperature is None:
        return None
    if 0 <= temperature <= 1:
        return temperature
    raise SystemExit("Temperature must be between 0 and 1.")


def normalize_endpoint(endpoint: str) -> str:
    trimmed = endpoint.rstrip("/")
    if trimmed.endswith("/openai/v1"):
        return trimmed[: -len("/openai/v1")]
    return trimmed


def normalize_api_version(api_version: str) -> str:
    if api_version == "preview":
        return DEFAULT_API_VERSION
    return api_version


def build_client(endpoint: str, api_key: str, api_version: str) -> AzureOpenAI:
    normalized_endpoint = normalize_endpoint(endpoint)
    return AzureOpenAI(
        api_key=api_key,
        azure_endpoint=normalized_endpoint,
        api_version=normalize_api_version(api_version),
    )


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
                    "Azure deployment not found. Set --model or "
                    "AZURE_OPENAI_DEPLOYMENT_NAME to your actual Azure OpenAI "
                    "deployment name for gpt-4o-transcribe-diarize."
                ) from exc
            if exc.status_code == 400 and "chunking_strategy is required" in str(exc):
                raise SystemExit(
                    "The Azure transcription request requires chunking_strategy "
                    "for diarization models."
                ) from exc
            raise

    return format_transcript(result), elapsed


def main() -> None:
    load_dotenv()
    args = parse_args()

    endpoint = get_required_setting(args.endpoint, "AZURE_OPENAI_ENDPOINT")
    api_key = get_required_setting(args.api_key, "AZURE_OPENAI_API_KEY")
    model = get_optional_setting_from_names(
        args.model,
        (
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_OPENAI_TRANSCRIPTION_MODEL",
        ),
        DEFAULT_MODEL,
    )
    api_version = get_optional_setting(
        args.api_version,
        "AZURE_OPENAI_API_VERSION",
        DEFAULT_API_VERSION,
    )
    temperature = validate_temperature(
        get_optional_float_setting(args.temperature, "AZURE_OPENAI_TEMPERATURE")
    )

    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()

    if not input_dir.exists():
        raise SystemExit(f"Input folder does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise SystemExit(f"Input path is not a folder: {input_dir}")

    wav_files = sorted(input_dir.glob("*.wav"))
    if not wav_files:
        raise SystemExit(f"No .wav files found in: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    client = build_client(endpoint=endpoint, api_key=api_key, api_version=api_version)
    overall_started_at = time.perf_counter()

    for audio_path in wav_files:
        print(f"Transcribing {audio_path.name}...")
        transcript, elapsed = transcribe_file(
            client=client,
            audio_path=audio_path,
            model=model,
            language=args.language,
            temperature=temperature,
        )
        output_path = output_dir / f"{audio_path.stem}.txt"
        output_path.write_text(transcript + "\n", encoding="utf-8")
        print(
            f"Saved {output_path.name} "
            f"(request took {format_duration(elapsed)})"
        )

    print(
        f"Completed {len(wav_files)} transcription request(s) in "
        f"{format_duration(time.perf_counter() - overall_started_at)} total"
    )


if __name__ == "__main__":
    main()
