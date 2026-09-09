from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def read_runs(path: Path) -> list[dict[str, Any]]:
    runs = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not runs:
        raise ValueError("agent result file contains no runs")
    return runs


def summarize_variant(runs: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_scenario[str(run["scenario_id"])].append(run)
    first_passes = 0
    any_passes = 0
    all_passes = 0
    assertion_passed = 0
    assertion_total = 0
    critical_evaluated = 0
    critical_failures = 0
    for scenario_runs in by_scenario.values():
        ordered = sorted(scenario_runs, key=lambda row: int(row["repetition"]))
        passed = [bool(row["grade"]["passed"]) for row in ordered]
        first_passes += passed[0]
        any_passes += any(passed)
        all_passes += all(passed)
        assertion_passed += sum(
            int(row["grade"]["assertions_passed"]) for row in ordered
        )
        assertion_total += sum(int(row["grade"]["assertions_total"]) for row in ordered)
        for row in ordered:
            if row.get("critical_grade") is not None:
                critical_evaluated += 1
                critical_failures += not bool(row["critical_grade"]["passed"])
    scenario_count = len(by_scenario)
    return {
        "variant": variant,
        "scenarios": scenario_count,
        "runs": len(runs),
        "pass_at_1": first_passes / scenario_count,
        "pass_at_k": any_passes / scenario_count,
        "pass_power_k": all_passes / scenario_count,
        "assertion_pass_rate": assertion_passed / max(1, assertion_total),
        "critical_runs": critical_evaluated,
        "critical_failure_rate": (
            critical_failures / critical_evaluated if critical_evaluated else None
        ),
    }


def run(args: argparse.Namespace) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in read_runs(args.results):
        grouped[str(record["variant"])].append(record)
    summaries = [
        summarize_variant(records, variant)
        for variant, records in sorted(grouped.items())
    ]
    gold = next((row for row in summaries if row["variant"] == "gold"), None)
    if gold:
        for row in summaries:
            row["asr_propagation_loss_pass_at_1"] = gold["pass_at_1"] - row["pass_at_1"]
    report = {
        "scorer_version": "faultbridge-agent-scorer-v1",
        "variants": summaries,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    print(f"Wrote {args.output} and {csv_path}")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Score executable agent runs")
    command.add_argument("results", type=Path)
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/agent_summary.json")
    )
    return command


if __name__ == "__main__":
    run(parser().parse_args())
