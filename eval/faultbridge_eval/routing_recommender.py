from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def paired_winner(
    comparisons: list[dict[str, Any]],
    candidate: str,
    default: str,
    language_pair: str,
    condition: str,
) -> bool:
    return any(
        row["language_pair"] == language_pair
        and row["condition"] == condition
        and {row["provider_a"], row["provider_b"]} == {candidate, default}
        and row["lower_wer_winner"] == candidate
        for row in comparisons
    )


def recommend(
    asr: dict[str, Any],
    agent: dict[str, Any],
    *,
    default_provider: str,
    max_failure_rate: float,
    max_p95_seconds: float,
) -> list[dict[str, Any]]:
    agent_by_variant = {row["variant"]: row for row in agent.get("variants", [])}
    comparisons = asr.get("paired_comparisons", [])
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for group in asr.get("groups", []):
        cells.setdefault((group["language_pair"], group["condition"]), []).append(group)
    recommendations: list[dict[str, Any]] = []
    for (language_pair, condition), groups in sorted(cells.items()):
        eligible = []
        rejections: dict[str, list[str]] = {}
        for group in groups:
            provider = group["provider"]
            reasons: list[str] = []
            if group["failure_rate"] > max_failure_rate:
                reasons.append("provider failure budget exceeded")
            latency = group.get("post_audio_p95_seconds")
            if latency is not None and latency > max_p95_seconds:
                reasons.append("p95 post-audio latency budget exceeded")
            agent_result = agent_by_variant.get(provider)
            if agent_result is None:
                reasons.append("no executable agent result")
            elif not agent_result.get("critical_runs"):
                reasons.append("no critical safety assertions evaluated")
            elif agent_result.get("critical_failure_rate") != 0:
                reasons.append("critical safety gate failed")
            if reasons:
                rejections[provider] = reasons
            else:
                eligible.append(group)
        chosen = default_provider
        decision = "conservative default"
        if eligible:
            best = min(eligible, key=lambda row: row["normalized_wer"])
            if best["provider"] == default_provider:
                decision = "default has the lowest eligible WER"
            elif paired_winner(
                comparisons,
                best["provider"],
                default_provider,
                language_pair,
                condition,
            ):
                chosen = best["provider"]
                decision = "paired 95% interval supports lower WER with safety gates"
            else:
                decision = "candidate improvement is not supported by paired interval"
        recommendations.append(
            {
                "language_pair": language_pair,
                "condition": condition,
                "primary_provider": chosen,
                "fallback_provider": default_provider,
                "decision": decision,
                "rejections": rejections,
            }
        )
    return recommendations


def run(args: argparse.Namespace) -> None:
    asr = read_json(args.asr_summary)
    agent = read_json(args.agent_summary)
    policies = recommend(
        asr,
        agent,
        default_provider=args.default_provider,
        max_failure_rate=args.max_failure_rate,
        max_p95_seconds=args.max_p95_seconds,
    )
    output = {
        "status": "draft",
        "benchmark_version": "faultbridge-voice-v1",
        "default_provider": args.default_provider,
        "policies": policies,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; policies remain draft until human review")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Derive conservative whole-utterance ASR routes"
    )
    command.add_argument(
        "--asr-summary",
        type=Path,
        default=Path("eval/results/asr_summary.json"),
    )
    command.add_argument(
        "--agent-summary",
        type=Path,
        default=Path("eval/results/agent_summary.json"),
    )
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/routing_policy.json")
    )
    command.add_argument("--default-provider", default="sahara")
    command.add_argument("--max-failure-rate", type=float, default=0.01)
    command.add_argument("--max-p95-seconds", type=float, default=2.0)
    return command


if __name__ == "__main__":
    run(parser().parse_args())
