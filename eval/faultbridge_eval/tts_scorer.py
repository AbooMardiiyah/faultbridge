from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from faultbridge_eval.metrics import (
    ErrorCounts,
    SegmentLossCounts,
    character_errors,
    cluster_bootstrap_interval,
    segment_loss_counts,
    switch_context_recall,
    word_errors,
)
from faultbridge_eval.scorer import read_results
from faultbridge_eval.tts_runner import latest_records

SCORER_VERSION = "faultbridge-tts-scorer-v1"


def _total_errors(records: list[dict[str, Any]]) -> ErrorCounts:
    total = ErrorCounts()
    for record in records:
        total += record["word_counts"]
    return total


def _total_segments(records: list[dict[str, Any]]) -> SegmentLossCounts:
    total = SegmentLossCounts()
    for record in records:
        total += record["segment_counts"]
    return total


def score_transcript(
    generation: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    hypothesis = str(result.get("hypothesis", ""))
    word = word_errors(str(generation["reference"]), hypothesis, normalized=True)
    character = character_errors(
        str(generation["reference"]), hypothesis, normalized=True
    )
    segments = segment_loss_counts(str(generation["reference_tagged"]), hypothesis)
    return {
        "sample_id": generation["sample_id"],
        "prompt_id": generation["prompt_id"],
        "judge": result["provider"],
        "language_pair": generation["language_pair"],
        "gender": generation["gender"],
        "source_group": generation["source_group"],
        "status": result.get("status", "failed"),
        "word_counts": word,
        "character_counts": character,
        "segment_counts": segments,
        "wer": word.error_rate,
        "cer": character.error_rate,
        "exact_utterance": word.error_rate == 0.0,
        "hallucination_detected": word.insertions > 0,
        "transcript_loss_detected": word.deletions > 0,
        "segment_loss_detected": segments.lost_segments > 0,
        "switch_context_recall": switch_context_recall(
            str(generation["reference_tagged"]), hypothesis
        ),
    }


def summarize_transcripts(records: list[dict[str, Any]]) -> dict[str, Any]:
    words = _total_errors(records)
    characters = ErrorCounts()
    for record in records:
        characters += record["character_counts"]
    segments = _total_segments(records)

    def statistic(sampled: list[object]) -> float:
        return _total_errors(list(sampled)).error_rate

    low, high = cluster_bootstrap_interval(
        records, lambda record: str(record["source_group"]), statistic
    )
    denominator = len(records)
    return {
        "samples": denominator,
        "asr_judge_failures": sum(row["status"] != "ok" for row in records),
        "wer": words.error_rate,
        "wer_ci_low": low,
        "wer_ci_high": high,
        "cer": characters.error_rate,
        "substitution_rate": words.substitutions / max(1, words.reference_units),
        "transcript_loss_rate": words.deletions / max(1, words.reference_units),
        "hallucination_rate": words.insertions / max(1, words.reference_units),
        "hallucination_incidence": sum(row["hallucination_detected"] for row in records)
        / denominator,
        "transcript_loss_incidence": sum(
            row["transcript_loss_detected"] for row in records
        )
        / denominator,
        "segment_loss_rate": segments.loss_rate,
        "segment_loss_incidence": sum(row["segment_loss_detected"] for row in records)
        / denominator,
        "embedded_english_segment_loss_rate": segments.embedded_english_lost
        / max(1, segments.embedded_english_total),
        "matrix_segment_loss_rate": segments.matrix_lost
        / max(1, segments.matrix_total),
        "exact_utterance_accuracy": sum(row["exact_utterance"] for row in records)
        / denominator,
        "switch_context_recall": sum(row["switch_context_recall"] for row in records)
        / denominator,
    }


def summarize_generation(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[(str(record["language_pair"]), str(record["gender"]))].append(record)
    summaries = []
    for (language_pair, gender), rows in sorted(groups.items()):
        successful = [row for row in rows if row.get("status") == "ok"]
        summaries.append(
            {
                "language_pair": language_pair,
                "gender": gender,
                "attempts": len(rows),
                "generation_failures": len(rows) - len(successful),
                "generation_failure_rate": (len(rows) - len(successful)) / len(rows),
                "first_audio_p50_seconds": (
                    median(float(row["first_audio_seconds"]) for row in successful)
                    if successful
                    else None
                ),
                "audio_completion_p50_seconds": (
                    median(float(row["audio_completion_seconds"]) for row in successful)
                    if successful
                    else None
                ),
                "session_close_p50_seconds": (
                    median(float(row["session_close_seconds"]) for row in successful)
                    if successful
                    else None
                ),
                "realtime_factor_p50": (
                    median(float(row["realtime_factor"]) for row in successful)
                    if successful
                    else None
                ),
                "clipping_ratio_mean": (
                    sum(float(row["clipping_ratio"]) for row in successful)
                    / len(successful)
                    if successful
                    and all(row.get("clipping_ratio") is not None for row in successful)
                    else None
                ),
                "silence_ratio_mean": (
                    sum(float(row["silence_ratio"]) for row in successful)
                    / len(successful)
                    if successful
                    and all(row.get("silence_ratio") is not None for row in successful)
                    else None
                ),
            }
        )
    return summaries


def consensus_rows(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sample: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in scored:
        by_sample[str(record["sample_id"])].append(record)
    rows = []
    for sample_id, judgments in sorted(by_sample.items()):
        threshold = len(judgments) // 2 + 1
        rows.append(
            {
                "sample_id": sample_id,
                "language_pair": judgments[0]["language_pair"],
                "gender": judgments[0]["gender"],
                "judges": len(judgments),
                "median_wer": median(float(row["wer"]) for row in judgments),
                "hallucination_consensus": sum(
                    row["hallucination_detected"] for row in judgments
                )
                >= threshold,
                "transcript_loss_consensus": sum(
                    row["transcript_loss_detected"] for row in judgments
                )
                >= threshold,
                "segment_loss_consensus": sum(
                    row["segment_loss_detected"] for row in judgments
                )
                >= threshold,
            }
        )
    return rows


def run(args: argparse.Namespace) -> None:
    generation_by_id: dict[str, dict[str, Any]] = {}
    for path in args.generation:
        generation_by_id.update(latest_records(path))
    if not generation_by_id:
        raise ValueError("no TTS generation records found")
    successful = {
        sample_id: record
        for sample_id, record in generation_by_id.items()
        if record.get("status") == "ok"
    }
    results = read_results(args.asr_results)
    judges = sorted({str(record["provider"]) for record in results})
    if len(judges) < 2 and not args.allow_incomplete:
        raise ValueError("TTS scoring requires at least two independent ASR judges")
    if judges == ["sahara"] and not args.allow_incomplete:
        raise ValueError("Sahara ASR cannot be the sole judge of Sahara TTS")

    latest_result = {
        (str(record["provider"]), str(record["sample_id"])): record
        for record in results
    }
    scored: list[dict[str, Any]] = []
    for judge in judges:
        missing = set(successful) - {
            sample_id for provider, sample_id in latest_result if provider == judge
        }
        if missing and not args.allow_incomplete:
            raise ValueError(f"{judge} is missing {len(missing)} generated samples")
        for sample_id, generation in successful.items():
            result = latest_result.get((judge, sample_id))
            if result is None:
                continue
            if result.get("audio_sha256") != generation.get("audio_sha256"):
                raise ValueError(f"audio hash mismatch for {judge}/{sample_id}")
            scored.append(score_transcript(generation, result))
        for generation in generation_by_id.values():
            if generation.get("status") == "ok":
                continue
            scored.append(
                score_transcript(
                    generation,
                    {
                        "provider": judge,
                        "status": "generation_failed",
                        "hypothesis": "",
                    },
                )
            )

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in scored:
        groups[
            (str(record["judge"]), str(record["language_pair"]), str(record["gender"]))
        ].append(record)
    transcript_summaries = [
        {
            "judge": judge,
            "language_pair": language_pair,
            "gender": gender,
            **summarize_transcripts(rows),
        }
        for (judge, language_pair, gender), rows in sorted(groups.items())
    ]
    consensus = consensus_rows(scored)
    report = {
        "scorer_version": SCORER_VERSION,
        "complete": all(
            all((judge, sample_id) in latest_result for sample_id in successful)
            for judge in judges
        ),
        "definitions": {
            "hallucination": "ASR-aligned inserted words divided by reference words",
            "transcript_loss": "ASR-aligned deleted words divided by reference words",
            "segment_loss": "contiguous tagged language spans with no correctly aligned word",
            "accuracy": "exact normalized utterance match rate",
        },
        "judges": judges,
        "generation": summarize_generation(list(generation_by_id.values())),
        "transcript_fidelity": transcript_summaries,
        "consensus": {
            "samples": len(consensus),
            "median_wer": (
                median(row["median_wer"] for row in consensus) if consensus else None
            ),
            "hallucination_incidence": (
                sum(row["hallucination_consensus"] for row in consensus)
                / len(consensus)
                if consensus
                else None
            ),
            "transcript_loss_incidence": (
                sum(row["transcript_loss_consensus"] for row in consensus)
                / len(consensus)
                if consensus
                else None
            ),
            "segment_loss_incidence": (
                sum(row["segment_loss_consensus"] for row in consensus) / len(consensus)
                if consensus
                else None
            ),
        },
        "audit_candidates": consensus,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    csv_path = args.output.with_suffix(".csv")
    if transcript_summaries:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(transcript_summaries[0]))
            writer.writeheader()
            writer.writerows(transcript_summaries)
    print(f"Wrote {args.output} and {csv_path}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Score Sahara code-switched TTS")
    command.add_argument("--generation", type=Path, nargs="+", required=True)
    command.add_argument("--asr-results", type=Path, nargs="+", required=True)
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/tts_summary.json")
    )
    command.add_argument("--allow-incomplete", action="store_true")
    return command


if __name__ == "__main__":
    run(parser().parse_args())
