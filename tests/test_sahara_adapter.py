import asyncio
import base64
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from faultbridge.adapters.sahara import (
    SaharaStreamingSTT,
    SaharaStreamingTTS,
    language_code,
    pcm16_chunks,
    text_chunks,
)


class FakeSocket:
    def __init__(self, *, received: list[dict], streamed: list[dict] | None = None):
        self.received = list(received)
        self.streamed = list(streamed or [])
        self.sent: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def recv(self) -> str:
        return json.dumps(self.received.pop(0))

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self.streamed:
            raise StopAsyncIteration
        return json.dumps(self.streamed.pop(0))


class MissingCommitSocket(FakeSocket):
    async def recv(self) -> str:
        if self.received:
            return await super().recv()
        await asyncio.Future()
        raise AssertionError("unreachable")


class SaharaAdapterTests(unittest.TestCase):
    def test_maps_all_submission_language_pairs(self) -> None:
        self.assertEqual(language_code("Hausa-English"), "ha")
        self.assertEqual(language_code("Igbo-English"), "ig")
        self.assertEqual(language_code("Pidgin-English"), "pcm")
        self.assertEqual(language_code("Yoruba-English"), "yo")

    def test_chunks_preserve_audio(self) -> None:
        audio = bytes(range(256)) * 150
        chunks = pcm16_chunks(audio)
        self.assertEqual(b"".join(chunks), audio)
        self.assertTrue(all(1024 <= len(chunk) <= 32 * 1024 for chunk in chunks))

    def test_short_audio_is_padded_to_api_minimum(self) -> None:
        audio = b"\x01\x02" * 100
        chunks = pcm16_chunks(audio)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(len(chunks[0]), 1024)
        self.assertTrue(chunks[0].startswith(audio))

    def test_rejects_partial_pcm_sample(self) -> None:
        with self.assertRaises(ValueError):
            pcm16_chunks(b"\x00")

    def test_rejects_unknown_language_pair(self) -> None:
        with self.assertRaises(ValueError):
            language_code("French-English")

    def test_tts_chunks_respect_provider_limits(self) -> None:
        text = " ".join(
            ["FaultBridge explains the verified network status clearly."] * 8
        )
        chunks = text_chunks(text)
        self.assertTrue(all(10 <= len(chunk) <= 100 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


class SaharaLanguageContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_connection_always_selects_input_language(self) -> None:
        socket = FakeSocket(
            received=[{"message_type": "SESSION_CREATED"}],
            streamed=[
                {
                    "message_type": "COMMITTED_TRANSCRIPT",
                    "transcript_text": "network no dey work",
                }
            ],
        )
        with patch(
            "faultbridge.adapters.sahara.websockets.connect", return_value=socket
        ) as connect:
            transcript = await SaharaStreamingSTT(api_key="test-key").transcribe(
                b"\x00\x00" * 512,
                language_pair="Pidgin-English",
            )
        query = parse_qs(urlparse(connect.call_args.args[0]).query)
        self.assertEqual(query["use_language_asr_input"], ["pcm"])
        self.assertEqual(transcript, "network no dey work")

    async def test_tts_connection_always_selects_language_and_accent(self) -> None:
        audio = b"valid-wav-bytes"
        socket = FakeSocket(
            received=[
                {"message_type": "SESSION_CREATED"},
                {"message_type": "TEXT_CHUNK_ACK"},
                {
                    "message_type": "AUDIO_CHUNK",
                    "processing_status": "READY",
                    "audio_base_64": base64.b64encode(audio).decode("ascii"),
                },
                {"message_type": "COMMITTED_AUDIO"},
            ]
        )
        with patch(
            "faultbridge.adapters.sahara.websockets.connect", return_value=socket
        ) as connect:
            chunks = [
                chunk
                async for chunk in SaharaStreamingTTS(api_key="test-key").synthesize(
                    "We found the verified network fault.",
                    language="pcm",
                    accent="pidgin",
                )
            ]
        query = parse_qs(urlparse(connect.call_args.args[0]).query)
        self.assertEqual(query["voice_language"], ["pcm"])
        self.assertEqual(query["voice_accent"], ["pidgin"])
        self.assertEqual(chunks, [audio])

    async def test_tts_rejects_an_empty_language(self) -> None:
        generator = SaharaStreamingTTS(api_key="test-key").synthesize(
            "We found the verified network fault.",
            language=" ",
            accent="pidgin",
        )
        with self.assertRaisesRegex(ValueError, "language is required"):
            await anext(generator)

    async def test_tts_keeps_ready_audio_when_commit_summary_is_missing(self) -> None:
        audio = b"valid-wav-bytes"
        socket = MissingCommitSocket(
            received=[
                {"message_type": "SESSION_CREATED"},
                {"message_type": "TEXT_CHUNK_ACK"},
                {
                    "message_type": "AUDIO_CHUNK",
                    "processing_status": "READY",
                    "audio_base_64": base64.b64encode(audio).decode("ascii"),
                },
            ]
        )
        with patch(
            "faultbridge.adapters.sahara.websockets.connect", return_value=socket
        ):
            chunks = [
                chunk
                async for chunk in SaharaStreamingTTS(
                    api_key="test-key", commit_timeout_seconds=0.01
                ).synthesize(
                    "We found the verified network fault.",
                    language="pcm",
                    accent="pidgin",
                )
            ]

        self.assertEqual(chunks, [audio])


if __name__ == "__main__":
    unittest.main()
