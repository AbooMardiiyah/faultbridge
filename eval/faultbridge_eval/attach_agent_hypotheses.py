from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

PROVIDER_LABELS = {
    "sahara-file-sync": "asr_sahara",
    "faster-whisper": "asr_faster_whisper",
    "sbpn-base": "asr_sbpn",
    "meta-omniasr-ctc": "asr_omniasr",
}


def latest_results(paths: list[Path]) -> dict[tuple[str, str], dict[str, Any]]:
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
    return latest


def attach(
    panel_path: Path,
    audio_manifest: Path,
    result_paths: list[Path],
    output: Path,
) -> None:
    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    scenarios = {str(row["scenario_id"]): row for row in panel}
    with audio_manifest.open(newline="", encoding="utf-8") as stream:
        audio_rows = {row["sample_id"]: row for row in csv.DictReader(stream)}
    if {row["source_group"] for row in audio_rows.values()} != set(scenarios):
        raise ValueError("audio manifest does not match the frozen scenario panel")

    results = latest_results(result_paths)
    providers = sorted({provider for provider, _ in results})
    unknown = set(providers) - set(PROVIDER_LABELS)
    if unknown:
        raise ValueError(f"unlabelled ASR providers: {sorted(unknown)}")
    if set(providers) != set(PROVIDER_LABELS):
        missing = set(PROVIDER_LABELS) - set(providers)
        raise ValueError(f"missing downstream ASR providers: {sorted(missing)}")

    for provider in providers:
        provider_samples = {
            sample_id
            for result_provider, sample_id in results
            if result_provider == provider
        }
        missing = set(audio_rows) - provider_samples
        extra = provider_samples - set(audio_rows)
        if missing or extra:
            raise ValueError(
                f"{provider} panel mismatch: {len(missing)} missing, {len(extra)} extra"
            )
        for sample_id, audio_row in audio_rows.items():
            record = results[(provider, sample_id)]
            scenario = scenarios[audio_row["source_group"]]
            scenario["hypotheses"][PROVIDER_LABELS[provider]] = str(
                record.get("hypothesis", "")
            )
            scenario.setdefault("audio_evidence", {})[PROVIDER_LABELS[provider]] = {
                "sample_id": sample_id,
                "status": record.get("status"),
                "audio_sha256": audio_row["audio_sha256"],
                "result_input_sha256": hashlib.sha256(
                    json.dumps(record, sort_keys=True).encode()
                ).hexdigest(),
            }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(list(scenarios.values()), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Attached {len(providers)} ASR variants to {len(scenarios)} scenarios")


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Attach named ASR hypotheses to the downstream agent panel"
    )
    command.add_argument(
        "--panel", type=Path, default=Path("benchmark/telco_scenarios_audio.json")
    )
    command.add_argument(
        "--audio-manifest",
        type=Path,
        default=Path("benchmark/agent_audio_generated.csv"),
    )
    command.add_argument(
        "--output", type=Path, default=Path("eval/results/agent_audio_scenarios.json")
    )
    command.add_argument("results", nargs="+", type=Path)
    return command


if __name__ == "__main__":
    args = parser().parse_args()
    attach(args.panel, args.audio_manifest, args.results, args.output)
