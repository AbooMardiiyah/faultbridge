from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from faultbridge_eval.manifest import BenchmarkSample
from faultbridge_eval.metrics import segment_loss_counts
from faultbridge_eval.tts_audit import parser as audit_parser
from faultbridge_eval.tts_audit import portable_audio_path, target_phrase
from faultbridge_eval.tts_manifest import TTS_SETTINGS, select_prompts
from faultbridge_eval.tts_runner import (
    attempt_counts,
    generate,
    latest_records,
    merge_wav_chunks,
)
from faultbridge_eval.tts_scorer import (
    publishable_report,
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
    def test_later_failed_retry_does_not_replace_successful_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "generation.jsonl"
            log.write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in (
                        {"sample_id": "one", "status": "ok", "audio_path": "one.wav"},
                        {"sample_id": "one", "status": "failed", "error": "network"},
                    )
                ),
                encoding="utf-8",
            )

            latest = latest_records(log)

        self.assertEqual(latest["one"]["status"], "ok")

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

    def test_audit_defaults_to_official_sync_generation_log(self) -> None:
        args = audit_parser().parse_args([])

        self.assertEqual(
            args.generation, Path("eval/results/tts/sync_generation.jsonl")
        )

    def test_audit_uses_portable_audio_paths_inside_repository(self) -> None:
        audio = Path.cwd() / "benchmark" / "tts_audio" / "sample.wav"

        self.assertEqual(
            portable_audio_path(str(audio)), "benchmark/tts_audio/sample.wav"
        )

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

    def test_public_tts_report_excludes_clip_level_audit_decisions(self) -> None:
        public = publishable_report(
            {"complete": True, "audit_candidates": [{"sample_id": "restricted"}]}
        )

        self.assertEqual(public, {"complete": True})

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


class TTSGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_generation_records_paid_request_provenance(self) -> None:
        class FakeSyncTTS:
            endpoint = "https://infer.voice.intron.io/tts/v1/generate"
            output_format = "wav"

            def __init__(self, **_kwargs) -> None:
                self.credit_balance = None
                self.request_id = "text-123"
                self.rate_limit_headers = {"x-ratelimit-remaining": "28"}

            async def synthesize(self, _text, *, language, accent):
                self.language = language
                self.accent = accent
                yield wav_bytes(1000)

        prompt = {
            "prompt_id": "tts-one",
            "source_sample_id": "source-one",
            "source_audio_sha256": "a" * 64,
            "language_pair": "Pidgin-English",
            "language": "pcm",
            "accent": "pidgin",
            "text": "Network no dey work today.",
            "text_tagged": "[[EN]]Network[[/EN]] no dey work today.",
            "cmi": "20",
            "switch_points": "1",
            "source_group": "speaker-one",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("faultbridge_eval.tts_runner.SaharaSynchronousTTS", FakeSyncTTS),
        ):
            result = await generate(
                prompt,
                gender="female",
                repetition=1,
                audio_root=Path(directory),
                api_key="test-key",
                provenance={"code_commit": "abc"},
                commit_ack_timeout_seconds=2.0,
                transport="sync",
                attempt=1,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model_identifier"], "sahara-synchronous-tts")
        self.assertEqual(result["provider_request_id"], "text-123")
        self.assertEqual(result["rate_limit_headers"]["x-ratelimit-remaining"], "28")
        self.assertEqual(result["parameters"]["transport"], "synchronous-generate")


if __name__ == "__main__":
    unittest.main()
