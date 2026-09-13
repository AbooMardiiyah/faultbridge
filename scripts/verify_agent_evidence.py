from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify saved downstream agent benchmark evidence"
    )
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=Path("benchmark/results/agent_evidence_manifest.json"),
    )
    args = parser.parse_args()
    evidence = json.loads(args.evidence_manifest.read_text(encoding="utf-8"))
    failures: list[str] = []
    for item in evidence["files"]:
        path = Path(item["path"])
        if not path.is_file():
            failures.append(f"missing: {path}")
        elif sha256_file(path) != item["sha256"]:
            failures.append(f"hash mismatch: {path}")

    audio_manifest = Path(evidence["generated_audio"]["manifest"])
    with audio_manifest.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    expected_audio = int(evidence["generated_audio"]["samples"])
    if len(rows) != expected_audio:
        failures.append(
            f"audio sample count: expected {expected_audio}, found {len(rows)}"
        )
    for row in rows:
        path = audio_manifest.parent / row["audio_path"]
        if not path.is_file():
            failures.append(f"missing audio: {path}")
        elif sha256_file(path) != row["audio_sha256"]:
            failures.append(f"audio hash mismatch: {path}")

    run_path = Path(evidence["agent_runs"]["path"])
    run_count = sum(
        1 for line in run_path.read_text(encoding="utf-8").splitlines() if line
    )
    expected_runs = int(evidence["agent_runs"]["runs"])
    if run_count != expected_runs:
        failures.append(f"agent run count: expected {expected_runs}, found {run_count}")

    if failures:
        raise SystemExit("Evidence verification failed:\n" + "\n".join(failures))
    print(
        f"Verified {len(evidence['files'])} evidence files, "
        f"{len(rows)} WAVs, and {run_count} agent runs"
    )


if __name__ == "__main__":
    main()
