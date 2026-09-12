from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import faultbridge_eval.runner as runner_module
from faultbridge_eval.manifest import BenchmarkSample
from faultbridge_eval.providers import TranscriptionResult
from faultbridge_eval.runner import attempt_counts, existing_samples, run_sample


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

    def test_attempt_counts_include_failed_retries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provider.jsonl"
            path.write_text(
                "\n".join(
                    json.dumps({"sample_id": sample, "provider": provider})
                    for sample, provider in (
                        ("one", "provider"),
                        ("two", "other"),
                        ("one", "provider"),
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(attempt_counts(path, "provider"), {"one": 2})


class BenchmarkResultSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_runner_stops_after_failure_threshold(self) -> None:
        samples = [
            BenchmarkSample(
                sample_id=f"sample-{index}",
                audio_path=Path(f"sample-{index}.wav"),
                audio_sha256=str(index) * 64,
                language_pair="Hausa-English",
                reference="reference words",
                reference_tagged="reference [[EN]]words[[/EN]]",
                duration_seconds=2.0,
                cmi=50.0,
                switch_points=1,
                source_group=f"source-{index}",
                source_kind="natural",
                condition="clean-16khz",
            )
            for index in range(1, 6)
        ]
        failure = {
            "provider": "provider",
            "status": "failed",
            "hypothesis": "",
            "error_type": "RuntimeError",
            "error_message": "capacity unavailable",
        }
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(
                manifest=Path(directory) / "manifest.csv",
                output=Path(directory) / "results",
                provider="sahara",
                retry_failures=False,
                limit=None,
                sample_ids=None,
                max_consecutive_failures=2,
                min_request_interval=0,
            )
            with (
                patch.object(runner_module, "read_manifest", return_value=samples),
                patch.object(runner_module, "build_provider", return_value=_Provider()),
                patch.object(
                    runner_module,
                    "environment_provenance",
                    return_value={"manifest_sha256": "manifest"},
                ),
                patch.object(
                    runner_module,
                    "run_sample",
                    new=AsyncMock(return_value=failure.copy()),
                ) as run_sample_mock,
            ):
                await runner_module.run(args)

            records = (args.output / "provider.jsonl").read_text().splitlines()

        self.assertEqual(run_sample_mock.await_count, 2)
        self.assertEqual(len(records), 2)

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
