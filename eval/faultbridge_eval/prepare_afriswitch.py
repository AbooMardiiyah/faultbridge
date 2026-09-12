from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import wave
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faultbridge_eval.manifest import REQUIRED_COLUMNS, sha256_file
from faultbridge_eval.metrics import percentile, tagged_text_without_markers

LANGUAGES = {
    "hausa": "Hausa-English",
    "igbo": "Igbo-English",
    "pidgin": "Pidgin-English",
    "yoruba": "Yoruba-English",
}
DATASET_ID = "intronhealth/AfriSwitch"


@dataclass(frozen=True, slots=True)
class Candidate:
    index: int
    filename: str
    transcription: str
    transcription_tagged: str
    cmi: float
    switch_points: int
    duration: float
    stratum: tuple[str, str, str]


def stable_rank(seed: int, language: str, filename: str) -> str:
    value = f"{seed}:{language}:{filename}".encode()
    return hashlib.sha256(value).hexdigest()


def band(value: float, lower: float, upper: float) -> str:
    if value <= lower:
        return "low"
    if value <= upper:
        return "medium"
    return "high"


def switch_band(points: int) -> str:
    if points <= 2:
        return "1-2"
    if points <= 5:
        return "3-5"
    return "6+"


def source_group(filename: str) -> str:
    stem = Path(filename).stem
    pieces = stem.replace("-", "_").split("_")
    return "_".join(pieces[:2]) if len(pieces) > 1 else stem


def artifact_stem(candidate: Candidate) -> str:
    """Return a stable name even when AfriSwitch repeats a source filename."""
    return f"{candidate.index:06d}-{Path(candidate.filename).stem}"


def collect_candidates(dataset: Any) -> list[Candidate]:
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(dataset):
        rows.append(
            {
                "index": index,
                "filename": str(row["filename"]),
                "transcription": str(row["transcription"]),
                "transcription_tagged": str(row["transcription_tagged"]),
                "cmi": float(row["cmi"]),
                "switch_points": int(row["num_switch_points"]),
                "duration": float(row["duration"]),
            }
        )
    if not rows:
        raise ValueError("AfriSwitch returned no rows")
    cmi_values = [row["cmi"] for row in rows]
    durations = [row["duration"] for row in rows]
    cmi_cutoffs = percentile(cmi_values, 1 / 3), percentile(cmi_values, 2 / 3)
    duration_cutoffs = (
        percentile(durations, 1 / 3),
        percentile(durations, 2 / 3),
    )
    return [
        Candidate(
            **row,
            stratum=(
                band(row["cmi"], *cmi_cutoffs),
                switch_band(row["switch_points"]),
                band(row["duration"], *duration_cutoffs),
            ),
        )
        for row in rows
    ]


def stratified_selection(
    candidates: list[Candidate], count: int, *, seed: int, language: str
) -> list[Candidate]:
    if count > len(candidates):
        raise ValueError(f"requested {count} samples from only {len(candidates)} rows")
    strata: dict[tuple[str, str, str], deque[Candidate]] = defaultdict(deque)
    for candidate in candidates:
        strata[candidate.stratum].append(candidate)
    for values in strata.values():
        ordered = sorted(
            values,
            key=lambda item: stable_rank(seed, language, item.filename),
        )
        values.clear()
        values.extend(ordered)
    stratum_order = sorted(
        strata, key=lambda item: stable_rank(seed, language, "|".join(item))
    )
    selected: list[Candidate] = []
    while len(selected) < count:
        progress = False
        for stratum in stratum_order:
            if strata[stratum] and len(selected) < count:
                selected.append(strata[stratum].popleft())
                progress = True
        if not progress:
            raise RuntimeError("stratified sampler exhausted unexpectedly")
    return sorted(selected, key=lambda item: item.filename)


def write_pcm16_wav(audio: dict[str, Any], destination: Path) -> None:
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as error:
        raise RuntimeError(
            "run `make benchmark-install` before preparing audio"
        ) from error
    encoded = audio.get("bytes")
    source: Any = io.BytesIO(encoded) if encoded else audio.get("path")
    if not source:
        raise ValueError("AfriSwitch audio has neither bytes nor a path")
    samples, sample_rate = sf.read(source, dtype="float32", always_2d=True)
    if sample_rate != 16_000:
        raise ValueError(f"expected 16 kHz AfriSwitch audio, received {sample_rate}")
    mono = samples.mean(axis=1)
    pcm = (np.clip(mono, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm)


def load_stream(config: str, token: str) -> Any:
    try:
        from datasets import Audio, load_dataset
    except ImportError as error:
        raise RuntimeError("run `make benchmark-install` first") from error
    dataset = load_dataset(
        DATASET_ID,
        config,
        split="test",
        streaming=True,
        token=token,
    )
    return dataset.cast_column("audio", Audio(decode=False))


def prepare_language(
    config: str,
    language_pair: str,
    *,
    count: int,
    seed: int,
    token: str,
    output: Path,
) -> list[dict[str, str]]:
    print(f"{config}: scanning metadata", flush=True)
    metadata_stream = load_stream(config, token)
    selected = stratified_selection(
        collect_candidates(metadata_stream), count, seed=seed, language=config
    )
    print(f"{config}: selected {len(selected)} rows; materializing audio", flush=True)
    selected_by_index = {candidate.index: candidate for candidate in selected}
    rows: list[dict[str, str]] = []
    audio_root = output / "audio" / config
    for index, row in enumerate(load_stream(config, token)):
        candidate = selected_by_index.get(index)
        if candidate is None:
            continue
        stem = artifact_stem(candidate)
        destination = audio_root / f"{stem}.wav"
        write_pcm16_wav(row["audio"], destination)
        rows.append(
            {
                "sample_id": f"afriswitch-{config}-{stem}",
                "audio_path": str(destination.relative_to(output)),
                "audio_sha256": sha256_file(destination),
                "language_pair": language_pair,
                "reference": tagged_text_without_markers(candidate.transcription),
                "reference_tagged": candidate.transcription_tagged,
                "duration_seconds": str(candidate.duration),
                "cmi": str(candidate.cmi),
                "switch_points": str(candidate.switch_points),
                "source_group": source_group(candidate.filename),
                "source_kind": "natural-afriswitch",
                "condition": "clean-16khz",
            }
        )
        if len(rows) % 25 == 0 or len(rows) == count:
            print(f"{config}: materialized {len(rows)}/{count}", flush=True)
        if len(rows) == count:
            break
    if len(rows) != count:
        raise RuntimeError(
            f"materialized {len(rows)} of {count} selected {config} rows"
        )
    return rows


def run(args: argparse.Namespace) -> None:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise ValueError(
            "HF_TOKEN or HUGGINGFACE_TOKEN is required after accepting the "
            "AfriSwitch access conditions"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for config in args.languages:
        rows.extend(
            prepare_language(
                config,
                LANGUAGES[config],
                count=args.per_language,
                seed=args.seed,
                token=token,
                output=args.output,
            )
        )
    manifest = args.output / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=sorted(REQUIRED_COLUMNS),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {manifest} with {len(rows)} immutable samples")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Create the frozen stratified AfriSwitch panel"
    )
    command.add_argument("--output", type=Path, default=Path("benchmark"))
    command.add_argument("--per-language", type=int, default=100)
    command.add_argument("--seed", type=int, default=20260915)
    command.add_argument(
        "--languages",
        nargs="+",
        choices=sorted(LANGUAGES),
        default=sorted(LANGUAGES),
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
