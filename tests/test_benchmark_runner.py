from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from faultbridge_eval.manifest import BenchmarkSample
from faultbridge_eval.providers import TranscriptionResult
from faultbridge_eval.runner import existing_samples, run_sample


class _Provider:
    name = "provider"
    model_identifier = "model-v1"

    def parameters(self) -> dict[str, str]:
        return {"device": "cpu"}

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        return TranscriptionResult("recognized words", 1.25, 0.25, "request-1")


class BenchmarkResumeTests(unittest.TestCase):
    def write_result(self, root: Path) -> Path:
        path = root / "provider.jsonl"
        path.write_text(
            json.dumps(
                {
                    "sample_id": "one",
                    "provider": "provider",
                    "status": "ok",
                    "model_identifier": "model-v1",
                    "parameters": {"device": "cpu"},
                    "manifest_sha256": "abc",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def test_resume_accepts_identical_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            completed = existing_samples(
                self.write_result(Path(directory)),
                "provider",
                include_failures=False,
                model_identifier="model-v1",
                parameters={"device": "cpu"},
                manifest_sha256="abc",
            )

        self.assertEqual(completed, {"one"})

    def test_resume_rejects_changed_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_result(Path(directory))
            with self.assertRaisesRegex(ValueError, "different model"):
                existing_samples(
                    path,
                    "provider",
                    include_failures=False,
                    model_identifier="model-v1",
                    parameters={"device": "cuda"},
                    manifest_sha256="abc",
                )


class BenchmarkResultSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_result_has_one_unambiguous_hypothesis_field(self) -> None:
        sample = BenchmarkSample(
            sample_id="one",
            audio_path=Path("one.wav"),
            audio_sha256="a" * 64,
            language_pair="Hausa-English",
            reference="reference words",
            reference_tagged="reference [[EN]]words[[/EN]]",
            duration_seconds=2.0,
            cmi=50.0,
            switch_points=1,
            source_group="source",
            source_kind="natural",
            condition="clean-16khz",
        )

        record = await run_sample(_Provider(), sample, provenance={})

        self.assertEqual(record["hypothesis"], "recognized words")
        self.assertNotIn("transcript", record)
        self.assertEqual(record["provider_request_id"], "request-1")


if __name__ == "__main__":
    unittest.main()
