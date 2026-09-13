from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from faultbridge_eval.tts_runner import latest_records

CONTROLLER_FIELDS = (
    "assignment_id",
    "language_pair",
    "gender",
    "audio_path",
    "audio_sha256",
    "reference",
    "reference_tagged",
    "target_phrase",
    "automatic_flag_count",
)
RATING_FIELDS = (
    "assignment_id",
    "language_pair",
    "playback_order",
    "audio_path",
    "listener_id",
    "naturalness_1_to_5",
    "pronunciation_1_to_5",
    "code_switch_appropriateness_1_to_5",
    "missing_content_yes_no",
    "extra_content_yes_no",
    "typed_target_phrase",
    "reviewer_note",
)


def portable_audio_path(value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def stable_rank(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def target_phrase(tagged_reference: str) -> str:
    spans = re.findall(r"\[\[EN\]\](.*?)\[\[/EN\]\]", tagged_reference)
    if not spans:
        return ""
    return max((" ".join(span.split()) for span in spans), key=len)


def select_audit_samples(
    generation: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    per_cell: int,
    seed: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[(str(candidate["language_pair"]), str(candidate["gender"]))].append(
            candidate
        )
    selected = []
    for cell, rows in sorted(grouped.items()):
        eligible = [row for row in rows if row["sample_id"] in generation]
        if len(eligible) < per_cell:
            raise ValueError(f"{cell} has only {len(eligible)} auditable outputs")
        ordered = sorted(
            eligible,
            key=lambda row: (
                -sum(
                    bool(row[field])
                    for field in (
                        "hallucination_consensus",
                        "transcript_loss_consensus",
                        "segment_loss_consensus",
                    )
                ),
                stable_rank(seed, str(row["sample_id"])),
            ),
        )
        selected.extend(
            (generation[row["sample_id"]], row) for row in ordered[:per_cell]
        )
    return selected


def run(args: argparse.Namespace) -> None:
    generation = {
        sample_id: record
        for sample_id, record in latest_records(args.generation).items()
        if record.get("status") == "ok"
    }
    report = json.loads(args.summary.read_text(encoding="utf-8"))
    selected = select_audit_samples(
        generation,
        list(report.get("audit_candidates", [])),
        per_cell=args.per_cell,
        seed=args.seed,
    )
    controller_rows = []
    for index, (record, candidate) in enumerate(selected, start=1):
        flags = sum(
            bool(candidate[field])
            for field in (
                "hallucination_consensus",
                "transcript_loss_consensus",
                "segment_loss_consensus",
            )
        )
        controller_rows.append(
            {
                "assignment_id": f"tts-audit-{index:03d}",
                "language_pair": record["language_pair"],
                "gender": record["gender"],
                "audio_path": portable_audio_path(str(record["audio_path"])),
                "audio_sha256": record["audio_sha256"],
                "reference": record["reference"],
                "reference_tagged": record["reference_tagged"],
                "target_phrase": target_phrase(str(record["reference_tagged"])),
                "automatic_flag_count": flags,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=CONTROLLER_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(controller_rows)

    rating_path = args.output.with_name(f"{args.output.stem}_ratings.csv")
    rating_rows = sorted(
        controller_rows,
        key=lambda row: stable_rank(args.seed, str(row["assignment_id"])),
    )
    with rating_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RATING_FIELDS, lineterminator="\n")
        writer.writeheader()
        for order, row in enumerate(rating_rows, start=1):
            writer.writerow(
                {
                    "assignment_id": row["assignment_id"],
                    "language_pair": row["language_pair"],
                    "playback_order": order,
                    "audio_path": row["audio_path"],
                }
            )
    print(f"Wrote {args.output} and blinded rating sheet {rating_path}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Prepare the bilingual TTS audit")
    command.add_argument(
        "--generation",
        type=Path,
        default=Path("eval/results/tts/sync_generation.jsonl"),
    )
    command.add_argument(
        "--summary", type=Path, default=Path("eval/results/tts_summary.json")
    )
    command.add_argument(
        "--output",
        type=Path,
        default=Path("eval/results/tts/audit_controller.csv"),
    )
    command.add_argument("--per-cell", type=int, default=5)
    command.add_argument("--seed", type=int, default=20260915)
    return command


if __name__ == "__main__":
    run(parser().parse_args())
