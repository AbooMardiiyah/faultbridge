from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path

from faultbridge_eval.manifest import BenchmarkSample
from faultbridge_eval.metrics import segment_loss_counts
from faultbridge_eval.tts_audit import target_phrase
from faultbridge_eval.tts_manifest import TTS_SETTINGS, select_prompts
from faultbridge_eval.tts_runner import attempt_counts, merge_wav_chunks
from faultbridge_eval.tts_scorer import (
    score_transcript,
    summarize_generation,
    summarize_transcripts,
)


def wav_bytes(value: int, frames: int = 160) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as destination:
        destination.setnchannels(1)
        destination.setsampwidth(2)
        destination.setframerate(16_000)
        destination.writeframes(value.to_bytes(2, "little", signed=True) * frames)
    return output.getvalue()


class TTSMetricsTests(unittest.TestCase):
    def test_attempt_counts_survive_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "generation.jsonl"
            log.write_text(
                "\n".join(
                    json.dumps({"sample_id": sample_id})
                    for sample_id in ("one", "two", "one")
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertEqual(attempt_counts(log), {"one": 2, "two": 1})

    def test_audit_target_uses_longest_switched_span(self) -> None:
        tagged = "local [[EN]]network[[/EN]] words [[EN]]service unavailable[[/EN]]"
        self.assertEqual(target_phrase(tagged), "service unavailable")

    def test_segment_loss_counts_contiguous_language_spans(self) -> None:
        counts = segment_loss_counts("bawo [[EN]]network down[[/EN]] yau", "bawo yau")

        self.assertEqual(counts.total_segments, 3)
        self.assertEqual(counts.lost_segments, 1)
        self.assertEqual(counts.embedded_english_lost, 1)
        self.assertEqual(counts.matrix_lost, 0)

    def test_wav_chunks_are_merged_as_pcm_frames(self) -> None:
        combined = merge_wav_chunks([wav_bytes(0), wav_bytes(1000)])

        self.assertAlmostEqual(combined.duration_seconds, 0.02)
        self.assertEqual(combined.sample_rate, 16_000)
        with wave.open(io.BytesIO(combined.audio), "rb") as source:
            self.assertEqual(source.getnframes(), 320)

    def test_tts_summary_exposes_organizer_metrics(self) -> None:
        generation = {
            "sample_id": "one",
            "prompt_id": "prompt-one",
            "reference": "network no dey work today",
            "reference_tagged": "[[EN]]network[[/EN]] no dey work today",
            "language_pair": "Pidgin-English",
            "gender": "female",
            "source_group": "speaker-a",
        }
        hallucination = score_transcript(
            generation,
            {
                "provider": "independent-asr",
                "status": "ok",
                "hypothesis": "network no dey work today extra",
            },
        )
        transcript_loss = score_transcript(
            {**generation, "sample_id": "two"},
            {
                "provider": "independent-asr",
                "status": "ok",
                "hypothesis": "network work today",
            },
        )
        summary = summarize_transcripts([hallucination, transcript_loss])

        self.assertGreater(summary["hallucination_rate"], 0)
        self.assertGreater(summary["transcript_loss_rate"], 0)
        self.assertEqual(summary["exact_utterance_accuracy"], 0)

    def test_generation_summary_separates_audio_and_session_latency(self) -> None:
        summary = summarize_generation(
            [
                {
                    "language_pair": "Pidgin-English",
                    "gender": "female",
                    "status": "ok",
                    "first_audio_seconds": 2.0,
                    "audio_completion_seconds": 3.0,
                    "session_close_seconds": 13.0,
                    "realtime_factor": 0.5,
                    "clipping_ratio": 0.0,
                    "silence_ratio": 0.1,
                }
            ]
        )[0]

        self.assertEqual(summary["first_audio_p50_seconds"], 2.0)
        self.assertEqual(summary["audio_completion_p50_seconds"], 3.0)
        self.assertEqual(summary["session_close_p50_seconds"], 13.0)


class TTSPromptSelectionTests(unittest.TestCase):
    def test_panel_selects_each_supported_language(self) -> None:
        samples = []
        for index, language_pair in enumerate(TTS_SETTINGS):
            samples.append(
                BenchmarkSample(
                    sample_id=f"sample-{index}",
                    audio_path=Path(f"audio-{index}.wav"),
                    audio_sha256=str(index) * 64,
                    language_pair=language_pair,
                    reference="local words and network words",
                    reference_tagged="local words and [[EN]]network words[[/EN]]",
                    duration_seconds=2.0,
                    cmi=20.0,
                    switch_points=2,
                    source_group=f"speaker-{index}",
                    source_kind="natural-afriswitch",
                    condition="clean-16khz",
                )
            )

        selected = select_prompts(samples, per_language=1, seed=7)

        self.assertEqual(
            {sample.language_pair for sample in selected}, set(TTS_SETTINGS)
        )


if __name__ == "__main__":
    unittest.main()
