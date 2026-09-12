from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import struct
import time
import wave
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from faultbridge.adapters.sahara import SaharaStreamingTTS
from faultbridge_eval.manifest import REQUIRED_COLUMNS, sha256_file
from faultbridge_eval.runner import append_record, environment_provenance
from faultbridge_eval.tts_manifest import FIELDS

GENERATOR_VERSION = "faultbridge-tts-generator-v5"
RESUMABLE_GENERATOR_VERSIONS = {
    "faultbridge-tts-generator-v4",
    GENERATOR_VERSION,
}


@dataclass(frozen=True, slots=True)
class WavMeasurement:
    audio: bytes
    duration_seconds: float
    sample_rate: int
    channels: int
    sample_width: int
    clipping_ratio: float | None
    silence_ratio: float | None


def read_prompts(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"TTS prompt manifest is missing {sorted(missing)}")
        prompts = list(reader)
    identifiers = [row["prompt_id"] for row in prompts]
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("TTS prompt IDs must be non-empty and unique")
    return prompts


def merge_wav_chunks(chunks: list[bytes]) -> WavMeasurement:
    if not chunks:
        raise ValueError("TTS returned no audio chunks")
    parameters: tuple[int, int, int, str] | None = None
    frames: list[bytes] = []
    for index, chunk in enumerate(chunks, start=1):
        try:
            with wave.open(io.BytesIO(chunk), "rb") as source:
                current = (
                    source.getnchannels(),
                    source.getsampwidth(),
                    source.getframerate(),
                    source.getcomptype(),
                )
                if parameters is None:
                    parameters = current
                elif current != parameters:
                    raise ValueError("TTS WAV chunks use incompatible audio parameters")
                frames.append(source.readframes(source.getnframes()))
        except (EOFError, wave.Error) as error:
            raise ValueError(f"TTS audio chunk {index} is not a valid WAV") from error
    assert parameters is not None
    channels, sample_width, sample_rate, compression = parameters
    if compression != "NONE":
        raise ValueError(f"unsupported TTS WAV compression {compression}")
    pcm = b"".join(frames)
    output = io.BytesIO()
    with wave.open(output, "wb") as destination:
        destination.setnchannels(channels)
        destination.setsampwidth(sample_width)
        destination.setframerate(sample_rate)
        destination.writeframes(pcm)

    clipping_ratio = silence_ratio = None
    if sample_width == 2 and len(pcm) % 2 == 0:
        values = [value[0] for value in struct.iter_unpack("<h", pcm)]
        if values:
            clipping_ratio = sum(abs(value) >= 32760 for value in values) / len(values)
            silence_ratio = sum(abs(value) <= 327 for value in values) / len(values)
    frame_count = len(pcm) / (channels * sample_width)
    return WavMeasurement(
        audio=output.getvalue(),
        duration_seconds=frame_count / sample_rate,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        clipping_ratio=clipping_ratio,
        silence_ratio=silence_ratio,
    )


def latest_records(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return latest
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if "sample_id" not in record:
            raise ValueError(f"{path}:{line_number} has no sample_id")
        latest[str(record["sample_id"])] = record
    return latest


def attempt_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not path.exists():
        return counts
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if "sample_id" not in record:
            raise ValueError(f"{path}:{line_number} has no sample_id")
        sample_id = str(record["sample_id"])
        counts[sample_id] = counts.get(sample_id, 0) + 1
    return counts


async def generate(
    prompt: dict[str, str],
    *,
    gender: str,
    repetition: int,
    audio_root: Path,
    api_key: str,
    provenance: dict[str, Any],
    commit_ack_timeout_seconds: float,
    attempt: int,
) -> dict[str, Any]:
    sample_id = f"{prompt['prompt_id']}-{gender}-r{repetition}"
    tts = SaharaStreamingTTS(
        api_key=api_key,
        gender=gender,
        commit_timeout_seconds=commit_ack_timeout_seconds,
    )
    base: dict[str, Any] = {
        "generator_version": GENERATOR_VERSION,
        "provider": "sahara-tts",
        "model_identifier": "sahara-streaming-tts",
        "sample_id": sample_id,
        "prompt_id": prompt["prompt_id"],
        "source_sample_id": prompt["source_sample_id"],
        "source_audio_sha256": prompt["source_audio_sha256"],
        "language_pair": prompt["language_pair"],
        "language": prompt["language"],
        "accent": prompt["accent"],
        "gender": gender,
        "repetition": repetition,
        "attempt": attempt,
        "parameters": {
            "output_format": tts.output_format,
            "websocket_compression": "disabled",
            "stream_timeout_seconds": tts.timeout_seconds,
            "commit_ack_timeout_seconds": tts.commit_timeout_seconds,
        },
        "reference": prompt["text"],
        "reference_tagged": prompt["text_tagged"],
        "cmi": float(prompt["cmi"]),
        "switch_points": int(prompt["switch_points"]),
        "source_group": prompt["source_group"],
        "recorded_at": datetime.now(UTC).isoformat(),
        **provenance,
    }
    started = time.perf_counter()
    first_audio_seconds: float | None = None
    audio_completion_seconds: float | None = None
    chunks: list[bytes] = []
    try:
        async for chunk in tts.synthesize(
            prompt["text"], language=prompt["language"], accent=prompt["accent"]
        ):
            received_seconds = time.perf_counter() - started
            if first_audio_seconds is None:
                first_audio_seconds = received_seconds
            audio_completion_seconds = received_seconds
            chunks.append(chunk)
        measurement = merge_wav_chunks(chunks)
        destination = audio_root / gender / f"{sample_id}.wav"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(measurement.audio)
    except Exception as error:  # noqa: BLE001 - failures are benchmark outcomes
        return {
            **base,
            "status": "failed",
            "credit_balance_start": tts.credit_balance,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "first_audio_seconds": first_audio_seconds,
            "audio_completion_seconds": audio_completion_seconds,
            "session_close_seconds": time.perf_counter() - started,
        }
    elapsed = time.perf_counter() - started
    assert audio_completion_seconds is not None
    return {
        **base,
        "status": "ok",
        "credit_balance_start": tts.credit_balance,
        "audio_path": str(destination),
        "audio_sha256": sha256_file(destination),
        "duration_seconds": measurement.duration_seconds,
        "sample_rate": measurement.sample_rate,
        "channels": measurement.channels,
        "sample_width": measurement.sample_width,
        "clipping_ratio": measurement.clipping_ratio,
        "silence_ratio": measurement.silence_ratio,
        "first_audio_seconds": first_audio_seconds,
        "audio_completion_seconds": audio_completion_seconds,
        "session_close_seconds": elapsed,
        "realtime_factor": audio_completion_seconds / measurement.duration_seconds,
    }


def write_audio_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for record in records:
        if record.get("status") != "ok":
            continue
        audio_path = Path(str(record["audio_path"])).resolve()
        if not audio_path.is_file():
            raise ValueError(f"generated TTS audio is missing: {audio_path}")
        if sha256_file(audio_path) != record["audio_sha256"]:
            raise ValueError(f"generated TTS audio hash changed: {audio_path}")
        try:
            relative_audio = audio_path.relative_to(path.parent.resolve())
        except ValueError as error:
            raise ValueError(
                "TTS audio must be below the output manifest directory"
            ) from error
        rows.append(
            {
                "sample_id": record["sample_id"],
                "audio_path": str(relative_audio),
                "audio_sha256": record["audio_sha256"],
                "language_pair": record["language_pair"],
                "reference": record["reference"],
                "reference_tagged": record["reference_tagged"],
                "duration_seconds": record["duration_seconds"],
                "cmi": record["cmi"],
                "switch_points": record["switch_points"],
                "source_group": record["source_group"],
                "source_kind": "sahara-tts",
                "condition": f"sahara-{record['gender']}",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=sorted(REQUIRED_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("SAHARA_API_KEY", "")
    if not api_key:
        raise ValueError("SAHARA_API_KEY is required")
    if args.commit_ack_timeout <= 0:
        raise ValueError("commit acknowledgement timeout must be positive")
    if args.limit is not None and args.limit <= 0:
        raise ValueError("limit must be positive")
    if args.max_consecutive_failures <= 0:
        raise ValueError("maximum consecutive failures must be positive")
    if args.min_request_interval < 0:
        raise ValueError("minimum request interval cannot be negative")
    prompts = read_prompts(args.prompts)
    provenance = environment_provenance(args.prompts)
    provenance["prompt_manifest_sha256"] = provenance.pop("manifest_sha256")
    existing = latest_records(args.log)
    attempts = attempt_counts(args.log)
    all_work = [
        (prompt, gender, repetition)
        for prompt in prompts
        for gender in ("female", "male")
        for repetition in range(1, args.repetitions + 1)
    ]
    active_prompts = prompts
    if args.prompt_ids:
        requested = set(args.prompt_ids)
        available = {prompt["prompt_id"] for prompt in prompts}
        missing = requested - available
        if missing:
            raise ValueError(f"unknown TTS prompt IDs: {sorted(missing)}")
        active_prompts = [
            prompt for prompt in prompts if prompt["prompt_id"] in requested
        ]
    if args.pilot_per_language:
        if args.prompt_ids:
            raise ValueError("prompt IDs and pilot-per-language cannot be combined")
        first_by_language: dict[str, dict[str, str]] = {}
        for prompt in prompts:
            first_by_language.setdefault(prompt["language_pair"], prompt)
        active_prompts = list(first_by_language.values())
    work = [
        (prompt, gender, repetition)
        for prompt in active_prompts
        for gender in args.genders
        for repetition in range(1, args.repetitions + 1)
    ]
    expected_ids = {
        f"{prompt['prompt_id']}-{gender}-r{repetition}"
        for prompt, gender, repetition in all_work
    }
    unexpected = set(existing) - expected_ids
    if unexpected:
        raise ValueError(
            f"generation log contains {len(unexpected)} samples outside this panel"
        )
    for sample_id, record in existing.items():
        if (
            record.get("generator_version") not in RESUMABLE_GENERATOR_VERSIONS
            or record.get("prompt_manifest_sha256")
            != provenance["prompt_manifest_sha256"]
        ):
            raise ValueError(
                f"generation log configuration changed at {sample_id}; "
                "choose a new log path"
            )
    remaining = []
    for prompt, gender, repetition in work:
        sample_id = f"{prompt['prompt_id']}-{gender}-r{repetition}"
        previous = existing.get(sample_id)
        if previous is None or (args.retry_failures and previous.get("status") != "ok"):
            remaining.append((prompt, gender, repetition))
    if args.retry_failures:
        remaining.sort(
            key=lambda item: attempts.get(
                f"{item[0]['prompt_id']}-{item[1]}-r{item[2]}", 0
            )
        )
    if args.limit is not None:
        remaining = remaining[: args.limit]
    consecutive_failures = 0
    previous_request_started: float | None = None
    for index, (prompt, gender, repetition) in enumerate(remaining, start=1):
        if previous_request_started is not None:
            elapsed_since_start = time.monotonic() - previous_request_started
            if elapsed_since_start < args.min_request_interval:
                await asyncio.sleep(args.min_request_interval - elapsed_since_start)
        previous_request_started = time.monotonic()
        sample_id = f"{prompt['prompt_id']}-{gender}-r{repetition}"
        record = await generate(
            prompt,
            gender=gender,
            repetition=repetition,
            audio_root=args.audio_root.resolve(),
            api_key=api_key,
            provenance=provenance,
            commit_ack_timeout_seconds=args.commit_ack_timeout,
            attempt=attempts.get(sample_id, 0) + 1,
        )
        append_record(args.log, record)
        existing[str(record["sample_id"])] = record
        attempts[sample_id] = int(record["attempt"])
        print(f"[{index}/{len(remaining)}] {record['sample_id']}: {record['status']}")
        if record["status"] == "ok":
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= args.max_consecutive_failures:
                print(
                    "Paused after "
                    f"{consecutive_failures} consecutive provider failures; "
                    "resume after checking service status or credit"
                )
                break
    write_audio_manifest(args.output_manifest, list(existing.values()))
    failures = sum(record.get("status") != "ok" for record in existing.values())
    print(
        f"Wrote {args.output_manifest} from {len(existing)} attempts "
        f"({failures} failed)"
    )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Generate the frozen Sahara TTS panel"
    )
    command.add_argument(
        "--prompts", type=Path, default=Path("benchmark/tts_prompts.csv")
    )
    command.add_argument("--audio-root", type=Path, default=Path("benchmark/tts_audio"))
    command.add_argument(
        "--output-manifest", type=Path, default=Path("benchmark/tts_generated.csv")
    )
    command.add_argument(
        "--log", type=Path, default=Path("eval/results/tts/generation.jsonl")
    )
    command.add_argument(
        "--genders", nargs="+", choices=["female", "male"], default=["female", "male"]
    )
    command.add_argument("--repetitions", type=int, default=1)
    command.add_argument("--commit-ack-timeout", type=float, default=2.0)
    command.add_argument("--limit", type=int)
    command.add_argument(
        "--prompt-id",
        dest="prompt_ids",
        action="append",
        help="run only this frozen prompt ID; repeat to select more than one",
    )
    command.add_argument(
        "--min-request-interval",
        type=float,
        default=2.0,
        help="minimum seconds between WebSocket session starts (default: 2)",
    )
    command.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=3,
        help="pause after this many consecutive failures (default: 3)",
    )
    command.add_argument(
        "--pilot-per-language",
        action="store_true",
        help="select the first frozen prompt in each language for contract checks",
    )
    command.add_argument("--retry-failures", action="store_true")
    return command


if __name__ == "__main__":
    asyncio.run(run(parser().parse_args()))
