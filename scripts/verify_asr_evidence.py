from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Verify saved ASR benchmark evidence")
    parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=Path("benchmark/results/asr_evidence_manifest.json"),
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
    if failures:
        raise SystemExit("Evidence verification failed:\n" + "\n".join(failures))
    print(f"Verified {len(evidence['files'])} evidence files")


if __name__ == "__main__":
    main()
