import os
import unittest
from datetime import UTC, datetime

from faultbridge.adapters.base import ComplaintAnalysis
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.database import Database
from faultbridge.services.voice import VoicePipeline
from faultbridge.tools.telco import TelcoTools


class RecordingSTT:
    async def transcribe(self, pcm16_audio: bytes, *, language_pair: str) -> str:
        if not pcm16_audio or language_pair != "Pidgin-English":
            raise AssertionError("voice metadata was not passed to STT")
        return "I agree. My data no dey work; call me on 08031234567"


class RecordingTTS:
    async def synthesize(self, text: str, *, language: str, accent: str):
        if not text or language != "en" or accent != "pidgin":
            raise AssertionError("response metadata was not passed to TTS")
        yield b"audio-one"
        yield b"audio-two"


class RecordingAgentModel:
    async def analyze_complaint(
        self, transcript: str, *, default_language_pair: str
    ) -> ComplaintAnalysis:
        if "08031234567" in transcript or "[PHONE_REDACTED]" not in transcript:
            raise AssertionError("PII was not redacted before the agent boundary")
        return ComplaintAnalysis("data_unavailable", default_language_pair, True)

    async def confirms_resolution(self, transcript: str) -> bool:
        return "works" in transcript.lower()


class VoicePipelineIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is required for integration tests")
        cls.database = Database(database_url)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.database.close()

    def setUp(self) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                TRUNCATE network_incidents, accounts, call_sessions,
                         candidate_incidents, compensation_commands,
                         callback_commands, troubleshooting_playbooks
                RESTART IDENTITY CASCADE
                """
            )
        self.database.upsert_playbook(
            {
                "issue_type": "data_unavailable",
                "title": "Refresh registration",
                "steps": ["Toggle airplane mode for ten seconds"],
                "language_pair": None,
                "operator": None,
                "device_os": None,
                "status": "approved",
                "source_system": "test-runbook",
                "source_reference": "VOICE-1",
                "verified_at": datetime.now(UTC),
                "version": 1,
            }
        )
        self.pipeline = VoicePipeline(
            stt=RecordingSTT(),
            tts=RecordingTTS(),
            agent_model=RecordingAgentModel(),
            orchestrator=FaultBridgeOrchestrator(
                TelcoTools(self.database), "voice-test-secret-at-least-32-characters"
            ),
        )

    async def test_provider_neutral_audio_turn_reaches_domain_engine(self) -> None:
        result = await self.pipeline.start_call(
            pcm16_audio=b"\x00\x00" * 1024,
            caller_id="08030000001",
            area="Yaba",
            cell_id="LAG-001",
            default_language_pair="Pidgin-English",
            consent=True,
            voice_language="en",
            voice_accent="pidgin",
        )
        self.assertNotIn("08031234567", result.transcript)
        self.assertIn("[PHONE_REDACTED]", result.transcript)
        self.assertEqual(result.response_audio_chunks, (b"audio-one", b"audio-two"))
        self.assertEqual(result.call["symptom"], "data_unavailable")
        self.assertEqual(result.call["outcome"], "awaiting_verification")

    async def test_declined_consent_never_reaches_speech_or_model_provider(
        self,
    ) -> None:
        class ForbiddenProvider:
            def __getattr__(self, name: str):
                raise AssertionError(f"provider access is forbidden: {name}")

        pipeline = VoicePipeline(
            stt=ForbiddenProvider(),
            tts=RecordingTTS(),
            agent_model=ForbiddenProvider(),
            orchestrator=FaultBridgeOrchestrator(
                TelcoTools(self.database), "voice-test-secret-at-least-32-characters"
            ),
        )

        result = await pipeline.start_call(
            pcm16_audio=b"private audio",
            caller_id="08030000002",
            area="Yaba",
            cell_id="LAG-002",
            default_language_pair="Pidgin-English",
            consent=False,
            voice_language="en",
            voice_accent="pidgin",
        )

        self.assertEqual(result.transcript, "")
        self.assertEqual(result.call["symptom"], "unknown")
        self.assertEqual(result.call["outcome"], "consent_declined")


if __name__ == "__main__":
    unittest.main()
