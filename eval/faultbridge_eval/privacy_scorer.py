from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from faultbridge.services.privacy import find_pii, redact_text


def prf(true_positive: int, predicted: int, expected: int) -> dict[str, float]:
    precision = true_positive / predicted if predicted else float(expected == 0)
    recall = true_positive / expected if expected else float(predicted == 0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def run(args: argparse.Namespace) -> None:
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"expected": 0, "predicted": 0, "true_positive": 0}
    )
    cases = failures = leakages = false_positive_cases = false_negative_cases = 0
    cases_with_pii = 0
    for line_number, line in enumerate(
        args.cases.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        case: dict[str, Any] = json.loads(line)
        text = str(case["text"])
        expected = {
            (str(span["type"]), int(span["start"]), int(span["end"]))
            for span in case["expected_spans"]
        }
        predicted = {
            (match.pii_type, match.start, match.end) for match in find_pii(text)
        }
        cases += 1
        cases_with_pii += bool(expected)
        failures += expected != predicted
        false_positive_cases += bool(predicted - expected)
        false_negative_cases += bool(expected - predicted)
        for pii_type, _, _ in expected:
            totals[pii_type]["expected"] += 1
        for pii_type, _, _ in predicted:
            totals[pii_type]["predicted"] += 1
        for pii_type, _, _ in expected & predicted:
            totals[pii_type]["true_positive"] += 1
        redacted = redact_text(text)
        leakages += any(text[start:end] in redacted for _, start, end in expected)
    if not cases:
        raise ValueError(f"{args.cases} contains no PII evaluation cases")
    overall = {
        key: sum(counts[key] for counts in totals.values())
        for key in ("expected", "predicted", "true_positive")
    }
    report = {
        "scorer_version": "faultbridge-pii-scorer-v1",
        "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "cases": cases,
        "cases_with_pii": cases_with_pii,
        "negative_cases": cases - cases_with_pii,
        "exact_case_failure_rate": failures / cases,
        "false_positive_case_rate": false_positive_cases / cases,
        "false_negative_case_rate": false_negative_cases / cases,
        "leakage_count": leakages,
        "leakage_rate": leakages / cases,
        "overall": {
            **overall,
            **prf(overall["true_positive"], overall["predicted"], overall["expected"]),
        },
        "by_type": {
            pii_type: {
                **counts,
                **prf(counts["true_positive"], counts["predicted"], counts["expected"]),
            }
            for pii_type, counts in sorted(totals.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Score typed PII redaction spans")
    command.add_argument("--cases", type=Path, required=True)
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/privacy_summary.json")
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
