from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from faultbridge_eval.manifest import BenchmarkSample, read_manifest
from faultbridge_eval.metrics import (
    ErrorCounts,
    RoleErrorCounts,
    character_errors,
    cluster_bootstrap_interval,
    language_role_counts,
    percentile,
    switch_context_recall,
    word_errors,
)

SCORER_VERSION = "faultbridge-scorer-v1"


def read_results(paths: list[Path]) -> list[dict[str, Any]]:
    """Read JSONL results and keep the last attempt for each provider/sample."""
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            record = json.loads(line)
            try:
                key = (str(record["provider"]), str(record["sample_id"]))
            except KeyError as error:
                raise ValueError(
                    f"{path}:{line_number} lacks {error.args[0]}"
                ) from error
            latest[key] = record
    return list(latest.values())


def total_errors(records: list[dict[str, Any]], field: str) -> ErrorCounts:
    total = ErrorCounts()
    for record in records:
        total += record[field]
    return total


def total_role_errors(records: list[dict[str, Any]]) -> RoleErrorCounts:
    total = RoleErrorCounts()
    for record in records:
        total += record["role_counts"]
    return total


def score_record(sample: BenchmarkSample, result: dict[str, Any]) -> dict[str, Any]:
    hypothesis = str(result.get("hypothesis", ""))
    raw_word = word_errors(sample.reference, hypothesis, normalized=False)
    normalized_word = word_errors(sample.reference, hypothesis, normalized=True)
    raw_character = character_errors(sample.reference, hypothesis, normalized=False)
    normalized_character = character_errors(
        sample.reference, hypothesis, normalized=True
    )
    return {
        **result,
        "language_pair": sample.language_pair,
        "source_group": sample.source_group,
        "source_kind": sample.source_kind,
        "duration_seconds": sample.duration_seconds,
        "cmi": sample.cmi,
        "switch_points": sample.switch_points,
        "condition": sample.condition,
        "raw_word": raw_word,
        "normalized_word": normalized_word,
        "raw_character": raw_character,
        "normalized_character": normalized_character,
        "role_counts": language_role_counts(sample.reference_tagged, hypothesis),
        "macro_normalized_wer": normalized_word.error_rate,
        "switch_context_recall": switch_context_recall(
            sample.reference_tagged, hypothesis
        ),
    }


def summarize(
    records: list[dict[str, Any]], *, confidence_interval: bool = True
) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot summarize no records")
    normalized_word = total_errors(records, "normalized_word")
    raw_word = total_errors(records, "raw_word")
    normalized_character = total_errors(records, "normalized_character")
    raw_character = total_errors(records, "raw_character")
    roles = total_role_errors(records)

    def bootstrap_wer(sampled: list[object]) -> float:
        return total_errors(list(sampled), "normalized_word").error_rate

    low = high = None
    if confidence_interval:
        low, high = cluster_bootstrap_interval(
            records,
            lambda record: record["source_group"],
            bootstrap_wer,
        )
    latency = [
        float(record["elapsed_seconds"])
        for record in records
        if record.get("elapsed_seconds") is not None
    ]
    realtime_latency = [
        max(0.0, float(record["elapsed_seconds"]) - float(record["duration_seconds"]))
        for record in records
        if record.get("elapsed_seconds") is not None
        and record.get("parameters", {}).get("realtime_pacing") is True
    ]
    realtime_factors = [
        float(record["elapsed_seconds"]) / float(record["duration_seconds"])
        for record in records
        if record.get("elapsed_seconds") is not None
    ]
    embedded_rate = roles.embedded_english_rate
    matrix_rate = roles.matrix_rate
    failures = sum(record.get("status") != "ok" for record in records)
    return {
        "samples": len(records),
        "failures": failures,
        "failure_rate": failures / len(records),
        "normalized_wer": normalized_word.error_rate,
        "normalized_wer_ci_low": low,
        "normalized_wer_ci_high": high,
        "macro_normalized_wer": sum(
            record["macro_normalized_wer"] for record in records
        )
        / len(records),
        "raw_wer": raw_word.error_rate,
        "normalized_cer": normalized_character.error_rate,
        "raw_cer": raw_character.error_rate,
        "substitution_rate": normalized_word.substitutions
        / max(1, normalized_word.reference_units),
        "deletion_rate": normalized_word.deletions
        / max(1, normalized_word.reference_units),
        "insertion_rate": normalized_word.insertions
        / max(1, normalized_word.reference_units),
        "embedded_english_error": embedded_rate,
        "matrix_error": matrix_rate,
        "language_role_gap": abs(embedded_rate - matrix_rate),
        "switch_context_recall": sum(
            record["switch_context_recall"] for record in records
        )
        / len(records),
        "latency_p50_seconds": percentile(latency, 0.5) if latency else None,
        "latency_p90_seconds": percentile(latency, 0.9) if latency else None,
        "latency_p95_seconds": percentile(latency, 0.95) if latency else None,
        "latency_max_seconds": max(latency) if latency else None,
        "post_audio_p50_seconds": (
            percentile(realtime_latency, 0.5) if realtime_latency else None
        ),
        "post_audio_p95_seconds": (
            percentile(realtime_latency, 0.95) if realtime_latency else None
        ),
        "realtime_factor_p50": (
            percentile(realtime_factors, 0.5) if realtime_factors else None
        ),
        "realtime_factor_p95": (
            percentile(realtime_factors, 0.95) if realtime_factors else None
        ),
    }


def paired_comparison(
    provider_a: str,
    provider_b: str,
    language_pair: str,
    condition: str,
    records_a: dict[str, dict[str, Any]],
    records_b: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    common_ids = sorted(set(records_a) & set(records_b))
    pairs = [(records_a[sample_id], records_b[sample_id]) for sample_id in common_ids]
    if not pairs:
        raise ValueError("paired comparison requires common samples")

    def difference(sampled: list[object]) -> float:
        left = [pair[0] for pair in sampled]
        right = [pair[1] for pair in sampled]
        return (
            total_errors(left, "normalized_word").error_rate
            - total_errors(right, "normalized_word").error_rate
        )

    point = difference(list(pairs))
    low, high = cluster_bootstrap_interval(
        pairs,
        lambda pair: pair[0]["source_group"],
        difference,
    )
    winner = "inconclusive"
    if high < 0:
        winner = provider_a
    elif low > 0:
        winner = provider_b
    return {
        "provider_a": provider_a,
        "provider_b": provider_b,
        "language_pair": language_pair,
        "condition": condition,
        "paired_samples": len(pairs),
        "normalized_wer_difference_a_minus_b": point,
        "ci_low": low,
        "ci_high": high,
        "lower_wer_winner": winner,
    }


def equal_language_summary(
    groups: list[dict[str, Any]], provider: str, condition: str
) -> dict[str, Any]:
    rows = [
        row
        for row in groups
        if row["provider"] == provider and row["condition"] == condition
    ]
    metrics = (
        "normalized_wer",
        "macro_normalized_wer",
        "normalized_cer",
        "embedded_english_error",
        "matrix_error",
        "switch_context_recall",
        "failure_rate",
    )
    return {
        "provider": provider,
        "condition": condition,
        "languages": len(rows),
        **{
            metric: sum(float(row[metric]) for row in rows) / len(rows)
            for metric in metrics
        },
    }


def cmi_band(value: float) -> str:
    if value < 15:
        return "low-<15"
    if value <= 30:
        return "medium-15-30"
    return "high->30"


def switch_band(value: int) -> str:
    if value <= 2:
        return "1-2"
    if value <= 5:
        return "3-5"
    return "6+"


def sliced_summaries(scored_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slices: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for record in scored_records:
        base = (
            str(record["provider"]),
            str(record["language_pair"]),
            str(record["condition"]),
        )
        slices[(*base, "cmi", cmi_band(float(record["cmi"])))].append(record)
        slices[
            (*base, "switch_points", switch_band(int(record["switch_points"])))
        ].append(record)
    return [
        {
            "provider": provider,
            "language_pair": language_pair,
            "condition": condition,
            "dimension": dimension,
            "slice": value,
            **summarize(records, confidence_interval=False),
        }
        for (
            provider,
            language_pair,
            condition,
            dimension,
            value,
        ), records in sorted(slices.items())
    ]


def run(args: argparse.Namespace) -> None:
    sample_list = read_manifest(args.manifest)
    samples = {sample.sample_id: sample for sample in sample_list}
    results = read_results(args.results)
    providers = sorted({str(result["provider"]) for result in results})
    expected_ids = set(samples)
    for provider in providers:
        present = {
            str(result["sample_id"])
            for result in results
            if result["provider"] == provider
        }
        missing = expected_ids - present
        if missing and not args.allow_incomplete:
            raise ValueError(
                f"{provider} is missing {len(missing)} manifest samples; "
                "use --allow-incomplete only for development"
            )

    by_group: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_sample: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    all_scored: list[dict[str, Any]] = []
    for result in results:
        sample_id = str(result["sample_id"])
        if sample_id not in samples:
            raise ValueError(f"result references unknown sample {sample_id}")
        sample = samples[sample_id]
        scored = score_record(sample, result)
        key = (str(result["provider"]), sample.language_pair, sample.condition)
        by_group[key].append(scored)
        by_sample[key][sample_id] = scored
        all_scored.append(scored)

    groups = [
        {
            "provider": provider,
            "language_pair": language_pair,
            "condition": condition,
            **summarize(records),
        }
        for (provider, language_pair, condition), records in sorted(by_group.items())
    ]
    comparisons: list[dict[str, Any]] = []
    languages = sorted({sample.language_pair for sample in sample_list})
    conditions = sorted({sample.condition for sample in sample_list})
    for provider_a, provider_b in combinations(providers, 2):
        for language_pair in languages:
            for condition in conditions:
                left = by_sample.get((provider_a, language_pair, condition), {})
                right = by_sample.get((provider_b, language_pair, condition), {})
                if left and right:
                    comparisons.append(
                        paired_comparison(
                            provider_a,
                            provider_b,
                            language_pair,
                            condition,
                            left,
                            right,
                        )
                    )

    report = {
        "scorer_version": SCORER_VERSION,
        "manifest_samples": len(samples),
        "complete": all(
            sum(result["provider"] == provider for result in results) == len(samples)
            for provider in providers
        ),
        "groups": groups,
        "equal_language_macro": [
            equal_language_summary(groups, provider, condition)
            for provider in providers
            for condition in conditions
            if any(
                row["provider"] == provider and row["condition"] == condition
                for row in groups
            )
        ],
        "paired_comparisons": comparisons,
        "slices": sliced_summaries(all_scored),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    csv_path = args.output.with_suffix(".csv")
    if groups:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(groups[0]))
            writer.writeheader()
            writer.writerows(groups)
    print(f"Wrote {args.output} and {csv_path}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Score FaultBridge ASR results")
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("results", type=Path, nargs="+")
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/asr_summary.json")
    )
    command.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="permit partial provider panels for development only",
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
