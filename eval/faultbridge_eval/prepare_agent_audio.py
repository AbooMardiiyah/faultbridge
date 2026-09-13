from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from faultbridge_eval.tts_manifest import FIELDS, TTS_SETTINGS

CASES = (
    "consent-decline",
    "known-fault-eligible",
    "guided-playbook",
    "crowd-threshold",
    "missing-account",
    "pii-before-model",
)
ENGLISH_SUFFIXES = (
    "I consent to automated processing.",
    "Do not record or process this call.",
    "Call 0803 555 0101 or email privacy.case@example.com.",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tag_declared_english(text: str) -> str:
    tagged = text
    for phrase in ENGLISH_SUFFIXES:
        tagged = tagged.replace(phrase, f"[[EN]]{phrase}[[/EN]]")
    return tagged


def code_switch_stats(tagged: str) -> tuple[float, int]:
    words = re.findall(r"[\w@.]+", re.sub(r"\[\[/?EN\]\]", "", tagged))
    english = re.findall(r"\[\[EN\]\](.*?)\[\[/EN\]\]", tagged)
    english_words = sum(len(re.findall(r"[\w@.]+", span)) for span in english)
    cmi = 100 * min(english_words, len(words)) / max(1, len(words))
    return cmi, len(english)


def select_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        scenario
        for scenario in scenarios
        if any(
            str(scenario["scenario_id"]).endswith(f"-{case_name}")
            for case_name in CASES
        )
    ]
    if len(selected) != 24:
        raise ValueError(f"expected 24 downstream scenarios, found {len(selected)}")
    return selected


def write_panel(scenarios_path: Path, prompts_path: Path, panel_path: Path) -> None:
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))
    selected = select_scenarios(scenarios)
    source_hash = hashlib.sha256(scenarios_path.read_bytes()).hexdigest()
    prompt_fields = (*FIELDS, "source_text_sha256")
    rows: list[dict[str, Any]] = []
    panel: list[dict[str, Any]] = []
    for scenario in selected:
        scenario_id = str(scenario["scenario_id"])
        inputs = scenario["input"]
        text = str(inputs["transcript"])
        tagged = tag_declared_english(text)
        cmi, switch_points = code_switch_stats(tagged)
        language, accent = TTS_SETTINGS[str(inputs["language_pair"])]
        rows.append(
            {
                "prompt_id": f"downstream-{scenario_id}",
                "source_sample_id": scenario_id,
                "source_audio_sha256": "",
                "source_manifest_sha256": source_hash,
                "language_pair": inputs["language_pair"],
                "language": language,
                "accent": accent,
                "text": text,
                "text_tagged": tagged,
                "cmi": f"{cmi:.6f}",
                "switch_points": switch_points,
                "source_group": scenario_id,
                "source_text_sha256": sha256_text(text),
            }
        )
        frozen = json.loads(json.dumps(scenario, ensure_ascii=False))
        frozen["hypotheses"] = {}
        panel.append(frozen)

    prompts_path.parent.mkdir(parents=True, exist_ok=True)
    with prompts_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=prompt_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    panel_path.write_text(
        json.dumps(panel, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(rows)} prompts to {prompts_path} and frozen scenarios to "
        f"{panel_path}"
    )


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Freeze the speech-to-agent downstream panel"
    )
    command.add_argument(
        "--scenarios", type=Path, default=Path("benchmark/telco_scenarios.json")
    )
    command.add_argument(
        "--prompts", type=Path, default=Path("benchmark/agent_audio_prompts.csv")
    )
    command.add_argument(
        "--panel", type=Path, default=Path("benchmark/telco_scenarios_audio.json")
    )
    return command


if __name__ == "__main__":
    args = parser().parse_args()
    write_panel(args.scenarios, args.prompts, args.panel)
