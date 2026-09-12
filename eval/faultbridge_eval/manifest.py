from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    audio_path: Path
    audio_sha256: str
    language_pair: str
    reference: str
    reference_tagged: str
    duration_seconds: float
    cmi: float
    switch_points: int
    source_group: str
    source_kind: str
    condition: str


REQUIRED_COLUMNS = {
    "sample_id",
    "audio_path",
    "audio_sha256",
    "language_pair",
    "reference",
    "reference_tagged",
    "duration_seconds",
    "cmi",
    "switch_points",
    "source_group",
    "source_kind",
    "condition",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path, *, verify_audio: bool = True) -> list[BenchmarkSample]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"manifest is missing columns: {', '.join(sorted(missing))}"
            )
        rows = list(reader)

    root = path.parent.resolve()
    samples: list[BenchmarkSample] = []
    seen: set[str] = set()
    seen_audio_paths: set[Path] = set()
    for row in rows:
        sample_id = row["sample_id"].strip()
        if not sample_id or sample_id in seen:
            raise ValueError(f"invalid or duplicate sample_id {sample_id!r}")
        seen.add(sample_id)
        audio_path = (root / row["audio_path"]).resolve()
        if not audio_path.is_relative_to(root):
            raise ValueError(f"audio path escapes the manifest directory: {sample_id}")
        if audio_path in seen_audio_paths:
            raise ValueError(f"duplicate audio path for {sample_id}: {audio_path}")
        seen_audio_paths.add(audio_path)
        expected_hash = row["audio_sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError(f"invalid audio_sha256 for {sample_id}")
        if verify_audio:
            if not audio_path.is_file():
                raise ValueError(f"audio is missing for {sample_id}: {audio_path}")
            actual_hash = sha256_file(audio_path)
            if actual_hash != expected_hash:
                raise ValueError(f"audio hash mismatch for {sample_id}")
        duration_seconds = float(row["duration_seconds"])
        cmi = float(row["cmi"])
        switch_points = int(row["switch_points"])
        if duration_seconds <= 0 or cmi < 0 or switch_points < 0:
            raise ValueError(f"invalid metrics for {sample_id}")
        if not row["reference"].strip():
            raise ValueError(f"empty reference for {sample_id}")
        samples.append(
            BenchmarkSample(
                sample_id=sample_id,
                audio_path=audio_path,
                audio_sha256=expected_hash,
                language_pair=row["language_pair"].strip(),
                reference=row["reference"],
                reference_tagged=row["reference_tagged"],
                duration_seconds=duration_seconds,
                cmi=cmi,
                switch_points=switch_points,
                source_group=row["source_group"].strip(),
                source_kind=row["source_kind"].strip(),
                condition=row["condition"].strip(),
            )
        )
    return samples
