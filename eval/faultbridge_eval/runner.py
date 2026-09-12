from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from faultbridge.adapters.sahara import SaharaStreamingSTT
from faultbridge_eval.manifest import BenchmarkSample, read_manifest
from faultbridge_eval.providers import (
    AssemblyAIStreamingTranscriber,
    BenchmarkTranscriber,
    FasterWhisperTranscriber,
    OmniASRCTCTranscriber,
    SaharaBenchmarkTranscriber,
    SaharaFileTranscriber,
    SBPNTranscriber,
)


def existing_samples(
    path: Path,
    provider: str,
    *,
    include_failures: bool,
    model_identifier: str | None = None,
    parameters: dict[str, Any] | None = None,
    manifest_sha256: str | None = None,
) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if model_identifier is not None and (
            record.get("model_identifier") != model_identifier
            or record.get("parameters") != parameters
            or record.get("manifest_sha256") != manifest_sha256
        ):
            raise ValueError(
                f"{path} contains results from a different model, configuration, "
                "or manifest; choose a new output directory"
            )
        if record.get("provider") == provider and (
            include_failures or record.get("status") == "ok"
        ):
            completed.add(record["sample_id"])
    return completed


def append_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def attempt_counts(path: Path, provider: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("provider") == provider:
            sample_id = str(record["sample_id"])
            counts[sample_id] = counts.get(sample_id, 0) + 1
    return counts


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
    if args.provider == "sahara-file":
        return SaharaFileTranscriber(api_key=os.environ.get("SAHARA_API_KEY", ""))
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
    if args.provider == "sbpn":
        return SBPNTranscriber(args.sbpn_model, device=args.sbpn_device)
    if args.provider == "omniasr":
        return OmniASRCTCTranscriber(
            args.omni_model,
            device=None if args.omni_device == "auto" else args.omni_device,
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
        client = getattr(provider, "client", None)
        credit_balance = getattr(client, "credit_balance", None)
        return {
            **base,
            "status": "failed",
            "hypothesis": "",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "elapsed_seconds": None,
            "first_partial_seconds": None,
            **(
                {"credit_balance_start": credit_balance}
                if credit_balance is not None
                else {}
            ),
        }
    return {
        **base,
        "status": "ok",
        "hypothesis": result.transcript,
        "elapsed_seconds": result.elapsed_seconds,
        "first_partial_seconds": result.first_partial_seconds,
        "provider_request_id": result.provider_request_id,
        **result.provider_metadata,
    }


async def run(args: argparse.Namespace) -> None:
    if args.limit is not None and args.limit <= 0:
        raise ValueError("limit must be positive")
    if args.max_consecutive_failures is not None and args.max_consecutive_failures < 0:
        raise ValueError("maximum consecutive failures cannot be negative")
    if args.min_request_interval is not None and args.min_request_interval < 0:
        raise ValueError("minimum request interval cannot be negative")
    samples = read_manifest(args.manifest)
    language_pairs = getattr(args, "language_pairs", None)
    if language_pairs:
        requested_pairs = {pair.casefold() for pair in language_pairs}
        available_pairs = {sample.language_pair.casefold() for sample in samples}
        missing_pairs = requested_pairs - available_pairs
        if missing_pairs:
            raise ValueError(
                f"unknown benchmark language pairs: {sorted(missing_pairs)}"
            )
        samples = [
            sample
            for sample in samples
            if sample.language_pair.casefold() in requested_pairs
        ]
    provider = build_provider(args)
    output = args.output / f"{provider.name}.jsonl"
    provenance = environment_provenance(args.manifest)
    completed = existing_samples(
        output,
        provider.name,
        include_failures=not args.retry_failures,
        model_identifier=provider.model_identifier,
        parameters=provider.parameters(),
        manifest_sha256=provenance["manifest_sha256"],
    )
    attempts = attempt_counts(output, provider.name)
    if args.sample_ids:
        requested = set(args.sample_ids)
        available = {sample.sample_id for sample in samples}
        missing = requested - available
        if missing:
            raise ValueError(f"unknown benchmark sample IDs: {sorted(missing)}")
        samples = [sample for sample in samples if sample.sample_id in requested]
    remaining = [sample for sample in samples if sample.sample_id not in completed]
    if args.retry_failures:
        remaining.sort(key=lambda sample: attempts.get(sample.sample_id, 0))
    if args.limit is not None:
        remaining = remaining[: args.limit]
    maximum_failures = args.max_consecutive_failures
    if maximum_failures is None:
        maximum_failures = (
            3 if args.provider in {"sahara", "sahara-file", "assemblyai"} else 0
        )
    request_interval = args.min_request_interval
    if request_interval is None:
        request_interval = 2.1 if args.provider in {"sahara", "sahara-file"} else 0.0
    consecutive_failures = 0
    previous_request_started: float | None = None
    for index, sample in enumerate(remaining, start=1):
        if previous_request_started is not None:
            elapsed_since_start = time.monotonic() - previous_request_started
            if elapsed_since_start < request_interval:
                await asyncio.sleep(request_interval - elapsed_since_start)
        previous_request_started = time.monotonic()
        record = await run_sample(provider, sample, provenance=provenance)
        record["attempt"] = attempts.get(sample.sample_id, 0) + 1
        append_record(output, record)
        attempts[sample.sample_id] = int(record["attempt"])
        print(
            f"[{index}/{len(remaining)}] {provider.name} {sample.sample_id}: "
            f"{record['status']}"
        )
        if record["status"] == "ok":
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if maximum_failures and consecutive_failures >= maximum_failures:
                print(
                    "Paused after "
                    f"{consecutive_failures} consecutive provider failures; "
                    "resume after checking service status or credit"
                )
                break


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
        choices=[
            "sahara",
            "sahara-file",
            "assemblyai",
            "faster-whisper",
            "sbpn",
            "omniasr",
        ],
        required=True,
    )
    command.add_argument("--assemblyai-model", default="whisper-rt")
    command.add_argument("--no-realtime-pacing", action="store_true")
    command.add_argument(
        "--retry-failures",
        action="store_true",
        help="append one retry for failed samples; successful samples still resume",
    )
    command.add_argument("--whisper-model", default="large-v3-turbo")
    command.add_argument("--whisper-device", default="cpu")
    command.add_argument("--whisper-compute-type", default="int8")
    command.add_argument("--sbpn-model", default="ogunlao/SBPN_multilingual_base")
    command.add_argument("--sbpn-device", choices=["cpu", "cuda"], default="cpu")
    command.add_argument("--omni-model", default="omniASR_CTC_300M_v2")
    command.add_argument("--omni-device", default="auto")
    command.add_argument(
        "--limit", type=int, help="run only the first N remaining samples for a pilot"
    )
    command.add_argument(
        "--sample-id",
        dest="sample_ids",
        action="append",
        help="run only this frozen sample ID; repeat to select more than one",
    )
    command.add_argument(
        "--language-pair",
        dest="language_pairs",
        action="append",
        help="run only this manifest language pair; repeat to select more than one",
    )
    command.add_argument(
        "--max-consecutive-failures",
        type=int,
        help="pause after N failures; defaults to 3 for remote providers, 0 otherwise",
    )
    command.add_argument(
        "--min-request-interval",
        type=float,
        help="minimum seconds between starts; defaults to 2 for Sahara, 0 otherwise",
    )
    return command


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
