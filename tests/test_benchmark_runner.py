from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from faultbridge_eval.runner import existing_samples


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


if __name__ == "__main__":
    unittest.main()
