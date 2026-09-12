from __future__ import annotations

import csv
import tempfile
import unittest
import wave
from pathlib import Path

from faultbridge_eval.manifest import REQUIRED_COLUMNS, read_manifest, sha256_file


class ManifestTests(unittest.TestCase):
    def write_fixture(self, root: Path, audio_hash: str | None = None) -> Path:
        audio = root / "audio.wav"
        with wave.open(str(audio), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(b"\x00\x00" * 160)
        row = {
            "sample_id": "one",
            "audio_path": "audio.wav",
            "audio_sha256": audio_hash or sha256_file(audio),
            "language_pair": "Yoruba-English",
            "reference": "network ko ṣiṣẹ",
            "reference_tagged": "[[EN]]network[[/EN]] ko ṣiṣẹ",
            "duration_seconds": "0.01",
            "cmi": "12.5",
            "switch_points": "2",
            "source_group": "speaker-a",
            "source_kind": "natural",
            "condition": "clean-16khz",
        }
        manifest = root / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
            writer.writeheader()
            writer.writerow(row)
        return manifest

    def test_manifest_verifies_audio_and_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            samples = read_manifest(self.write_fixture(Path(directory)))

        self.assertEqual(samples[0].sample_id, "one")
        self.assertEqual(samples[0].switch_points, 2)

    def test_manifest_rejects_changed_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_fixture(Path(directory), "0" * 64)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_manifest(manifest)

    def test_manifest_rejects_duplicate_audio_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self.write_fixture(Path(directory))
            with manifest.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            duplicate = {**rows[0], "sample_id": "two"}
            with manifest.open("a", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED_COLUMNS))
                writer.writerow(duplicate)

            with self.assertRaisesRegex(ValueError, "duplicate audio path"):
                read_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
