from __future__ import annotations

import argparse
import csv
import json
import tempfile
import unittest
import wave
from pathlib import Path

from faultbridge_eval import agent_scorer, scorer
from faultbridge_eval.manifest import REQUIRED_COLUMNS, sha256_file


class EvaluationScorerTests(unittest.TestCase):
    def write_manifest(self, root: Path) -> Path:
        rows = []
        for index, reference in enumerate(("network down", "service works"), start=1):
            audio = root / f"{index}.wav"
            with wave.open(str(audio), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16_000)
                output.writeframes(b"\x00\x00" * 160)
            rows.append(
                {
                    "sample_id": str(index),
                    "audio_path": audio.name,
                    "audio_sha256": sha256_file(audio),
                    "language_pair": "Pidgin-English",
                    "reference": reference,
                    "reference_tagged": f"[[EN]]{reference}[[/EN]]",
                    "duration_seconds": "0.01",
                    "cmi": "20",
                    "switch_points": "1",
                    "source_group": f"source-{index}",
                    "source_kind": "natural",
                    "condition": "clean-16khz",
                }
            )
        manifest = root / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
            writer.writeheader()
            writer.writerows(rows)
        return manifest

    def test_asr_scorer_writes_paired_complete_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.write_manifest(root)
            paths = []
            for provider, hypotheses in {
                "a": ("network down", "service works"),
                "b": ("network gone", "service works"),
            }.items():
                path = root / f"{provider}.jsonl"
                path.write_text(
                    "".join(
                        json.dumps(
                            {
                                "provider": provider,
                                "sample_id": str(index),
                                "status": "ok",
                                "hypothesis": hypothesis,
                                "elapsed_seconds": 1.0,
                            }
                        )
                        + "\n"
                        for index, hypothesis in enumerate(hypotheses, start=1)
                    ),
                    encoding="utf-8",
                )
                paths.append(path)
            output = root / "report.json"

            scorer.run(
                argparse.Namespace(
                    manifest=manifest,
                    results=paths,
                    output=output,
                    allow_incomplete=False,
                )
            )
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(report["complete"])
        self.assertEqual(len(report["paired_comparisons"]), 1)
        self.assertEqual(report["groups"][0]["normalized_wer"], 0.0)

    def test_agent_scorer_computes_repeated_run_reliability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "runs.jsonl"
            records = []
            for variant, passes in {
                "gold": [True, True, True],
                "asr": [True, False, False],
            }.items():
                for repetition, passed in enumerate(passes, start=1):
                    records.append(
                        {
                            "scenario_id": "scenario-1",
                            "language_pair": "Pidgin-English",
                            "variant": variant,
                            "repetition": repetition,
                            "agent_model_seconds": float(repetition),
                            "grade": {
                                "passed": passed,
                                "assertions_passed": int(passed),
                                "assertions_total": 1,
                            },
                        }
                    )
            results.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            output = root / "agent.json"

            agent_scorer.run(argparse.Namespace(results=results, output=output))
            report = json.loads(output.read_text(encoding="utf-8"))

        asr = next(row for row in report["variants"] if row["variant"] == "asr")
        self.assertEqual(asr["pass_at_1"], 1.0)
        self.assertEqual(asr["pass_at_k"], 1.0)
        self.assertEqual(asr["pass_power_k"], 0.0)
        self.assertEqual(asr["asr_propagation_loss_pass_at_1"], 0.0)
        self.assertEqual(asr["voice_capability_retention"], 1.0)
        self.assertEqual(asr["agent_model_latency_p50_seconds"], 2.0)
        self.assertEqual(asr["agent_model_latency_p95_seconds"], 2.9)
        self.assertEqual(len(report["by_language"]), 2)


if __name__ == "__main__":
    unittest.main()
