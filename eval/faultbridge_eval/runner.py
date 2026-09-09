from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from faultbridge.adapters.sahara import SaharaStreamingSTT
from faultbridge_eval.manifest import BenchmarkSample, read_manifest
from faultbridge_eval.providers import (
    AssemblyAIStreamingTranscriber,
    BenchmarkTranscriber,
    FasterWhisperTranscriber,
    SaharaBenchmarkTranscriber,
)


def existing_samples(path: Path, provider: str, *, include_failures: bool) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("provider") == provider and (
            include_failures or record.get("status") == "ok"
        ):
            completed.add(record["sample_id"])
    return completed


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_provider(args: argparse.Namespace) -> BenchmarkTranscriber:
    if args.provider == "sahara":
        api_key = os.environ.get("SAHARA_API_KEY", "")
        return SaharaBenchmarkTranscriber(
            SaharaStreamingSTT(
                api_key=api_key,
                timeout_seconds=180.0,
                realtime_pacing=not args.no_realtime_pacing,
            )
        )
    if args.provider == "assemblyai":
        return AssemblyAIStreamingTranscriber(
            api_key=os.environ.get("ASSEMBLYAI_API_KEY", ""),
            model=args.assemblyai_model,
            realtime_pacing=not args.no_realtime_pacing,
        )
    if args.provider == "faster-whisper":
        return FasterWhisperTranscriber(
            args.whisper_model,
            device=args.whisper_device,
            compute_type=args.whisper_compute_type,
        )
    raise ValueError(f"unsupported provider {args.provider}")


async def run_sample(
    provider: BenchmarkTranscriber,
    sample: BenchmarkSample,
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "benchmark_version": "faultbridge-voice-v1",
        "provider": provider.name,
        "model_identifier": provider.model_identifier,
        "parameters": provider.parameters(),
        "sample_id": sample.sample_id,
        "audio_sha256": sample.audio_sha256,
        "language_pair": sample.language_pair,
        "recorded_at": datetime.now(UTC).isoformat(),
        **provenance,
    }
    try:
        result = await provider.transcribe(
            sample.audio_path, language_pair=sample.language_pair
        )
    except Exception as error:  # noqa: BLE001 - provider failure is a scored outcome
        return {
            **base,
            "status": "failed",
            "hypothesis": "",
            "error_type": type(error).__name__,
            "elapsed_seconds": None,
            "first_partial_seconds": None,
        }
    return {**base, "status": "ok", **asdict(result), "hypothesis": result.transcript}


async def run(args: argparse.Namespace) -> None:
    samples = read_manifest(args.manifest)
    provider = build_provider(args)
    output = args.output / f"{provider.name}.jsonl"
    completed = existing_samples(
        output, provider.name, include_failures=not args.retry_failures
    )
    remaining = [sample for sample in samples if sample.sample_id not in completed]
    provenance = environment_provenance(args.manifest)
    for index, sample in enumerate(remaining, start=1):
        record = await run_sample(provider, sample, provenance=provenance)
        append_record(output, record)
        print(
            f"[{index}/{len(remaining)}] {provider.name} {sample.sample_id}: "
            f"{record['status']}"
        )


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip()


def environment_provenance(manifest: Path) -> dict[str, Any]:
    return {
        "manifest_sha256": _file_hash(manifest),
        "code_commit": _commit(),
        "lock_sha256": _file_hash(Path("uv.lock")),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run a fixed FaultBridge ASR panel")
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--output", type=Path, default=Path("eval/results/raw"))
    command.add_argument(
        "--provider",
        choices=["sahara", "assemblyai", "faster-whisper"],
        required=True,
    )
    command.add_argument("--assemblyai-model", default="whisper-rt")
    command.add_argument("--no-realtime-pacing", action="store_true")
    command.add_argument(
        "--retry-failures",
        action="store_true",
        help="append one retry for failed samples; successful samples still resume",
    )
    command.add_argument("--whisper-model", default="large-v3")
    command.add_argument("--whisper-device", default="cpu")
    command.add_argument("--whisper-compute-type", default="int8")
    return command


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
