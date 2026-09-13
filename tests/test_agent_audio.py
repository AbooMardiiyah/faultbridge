from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from faultbridge_eval.attach_agent_hypotheses import PROVIDER_LABELS, attach
from faultbridge_eval.prepare_agent_audio import select_scenarios, write_panel
from faultbridge_eval.prepare_agent_scenarios import build_scenarios


class AgentAudioPanelTests(unittest.TestCase):
    def test_panel_is_balanced_and_uses_unique_domain_complaints(self) -> None:
        selected = select_scenarios(build_scenarios())

        self.assertEqual(len(selected), 24)
        self.assertEqual(
            Counter(row["input"]["language_pair"] for row in selected),
            {
                "Hausa-English": 6,
                "Igbo-English": 6,
                "Pidgin-English": 6,
                "Yoruba-English": 6,
            },
        )
        for language_pair in {row["input"]["language_pair"] for row in selected}:
            texts = [
                row["input"]["transcript"]
                for row in selected
                if row["input"]["language_pair"] == language_pair
            ]
            self.assertEqual(len(texts), len(set(texts)))

    def test_named_hypotheses_attach_only_after_complete_provider_panels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scenarios = root / "scenarios.json"
            prompts = root / "prompts.csv"
            panel = root / "panel.json"
            scenarios.write_text(json.dumps(build_scenarios()), encoding="utf-8")
            write_panel(scenarios, prompts, panel)
            with prompts.open(encoding="utf-8") as stream:
                prompt_rows = list(csv.DictReader(stream))
            audio_manifest = root / "audio.csv"
            fields = ("sample_id", "source_group", "audio_sha256")
            with audio_manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    {
                        "sample_id": f"{row['prompt_id']}-female-r1",
                        "source_group": row["source_group"],
                        "audio_sha256": "a" * 64,
                    }
                    for row in prompt_rows
                )
            result_paths = []
            for provider in PROVIDER_LABELS:
                path = root / f"{provider}.jsonl"
                path.write_text(
                    "".join(
                        json.dumps(
                            {
                                "provider": provider,
                                "sample_id": f"{row['prompt_id']}-female-r1",
                                "status": "ok",
                                "hypothesis": f"{provider} transcript",
                            }
                        )
                        + "\n"
                        for row in prompt_rows
                    ),
                    encoding="utf-8",
                )
                result_paths.append(path)
            output = root / "attached.json"

            attach(panel, audio_manifest, result_paths, output)
            attached = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(len(attached), 24)
        self.assertTrue(
            all(
                set(row["hypotheses"]) == set(PROVIDER_LABELS.values())
                for row in attached
            )
        )


if __name__ == "__main__":
    unittest.main()
