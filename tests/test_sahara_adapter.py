import asyncio
import base64
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx

from faultbridge.adapters.sahara import (
    SaharaError,
    SaharaStreamingSTT,
    SaharaStreamingTTS,
    SaharaSynchronousTTS,
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


class FakeHTTPClient:
    def __init__(
        self,
        *,
        post_responses: list[httpx.Response] | None = None,
        get_responses: list[httpx.Response] | None = None,
    ) -> None:
        self.post_responses = list(post_responses or [])
        self.get_responses = list(get_responses or [])
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url: str, **kwargs) -> httpx.Response:
        self.posts.append((url, kwargs))
        return self.post_responses.pop(0)

    async def get(self, url: str, **kwargs) -> httpx.Response:
        self.gets.append((url, kwargs))
        return self.get_responses.pop(0)


class SaharaAdapterTests(unittest.TestCase):
    def test_terminal_error_preserves_documented_limit(self) -> None:
        with self.assertRaisesRegex(SaharaError, '"chunk_size_max": "100"'):
            SaharaStreamingSTT._raise_for_error(
                {
                    "message_type": "CHUNK_SIZE_TOO_LARGE",
                    "chunk_size_max": "100",
                }
            )

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

    def test_tts_chunks_rebalance_a_short_tail_without_exceeding_limit(self) -> None:
        text = (
            "Wai su yan hip hop dinnan kullum sai sababbin abubuwa ne? Ai kasan "
            "hip hop, asalin hip hop, ai hio hop wato"
        )

        chunks = text_chunks(text)

        self.assertTrue(all(10 <= len(chunk) <= 100 for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


class SaharaLanguageContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_connection_always_selects_input_language(self) -> None:
        socket = FakeSocket(
            received=[{"message_type": "SESSION_CREATED", "credit_balance": 8.5}],
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
            client = SaharaStreamingSTT(api_key="test-key")
            transcript = await client.transcribe(
                b"\x00\x00" * 512,
                language_pair="Pidgin-English",
            )
        query = parse_qs(urlparse(connect.call_args.args[0]).query)
        self.assertEqual(query["use_language_asr_input"], ["pcm"])
        self.assertIsNone(connect.call_args.kwargs["compression"])
        self.assertEqual(connect.call_args.kwargs["max_queue"], 128)
        self.assertEqual(transcript, "network no dey work")
        self.assertEqual(client.credit_balance, 8.5)

    async def test_tts_connection_always_selects_language_and_accent(self) -> None:
        audio = b"valid-wav-bytes"
        socket = FakeSocket(
            received=[
                {"message_type": "SESSION_CREATED", "credit_balance": 9.75},
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
            tts = SaharaStreamingTTS(api_key="test-key")
            chunks = [
                chunk
                async for chunk in tts.synthesize(
                    "We found the verified network fault.",
                    language="pcm",
                    accent="pidgin",
                )
            ]
        query = parse_qs(urlparse(connect.call_args.args[0]).query)
        self.assertEqual(query["voice_language"], ["pcm"])
        self.assertEqual(query["voice_accent"], ["pidgin"])
        self.assertIsNone(connect.call_args.kwargs["compression"])
        self.assertEqual(chunks, [audio])
        self.assertEqual(tts.credit_balance, 9.75)

    async def test_sync_tts_sends_explicit_voice_and_downloads_without_token(
        self,
    ) -> None:
        api = FakeHTTPClient(
            post_responses=[
                httpx.Response(
                    200,
                    headers={"x-ratelimit-remaining": "29"},
                    json={
                        "status": "Ok",
                        "data": {
                            "text_id": "text-1",
                            "processing_status": "TTS_TEXT_AUDIO_GENERATED",
                            "audio_path": "https://audio.example/output.wav",
                        },
                    },
                )
            ]
        )
        download = FakeHTTPClient(
            get_responses=[httpx.Response(200, content=b"valid-wav-bytes")]
        )
        with patch(
            "faultbridge.adapters.sahara.httpx.AsyncClient",
            side_effect=[api, download],
        ):
            tts = SaharaSynchronousTTS(api_key="test-key", gender="male")
            chunks = [
                chunk
                async for chunk in tts.synthesize(
                    "Network no dey work today.",
                    language="pcm",
                    accent="pidgin",
                )
            ]

        request = api.posts[0][1]
        self.assertEqual(request["json"]["voice_language"], "pcm")
        self.assertEqual(request["json"]["voice_accent"], "pidgin")
        self.assertEqual(request["json"]["voice_gender"], "male")
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(download.gets, [("https://audio.example/output.wav", {})])
        self.assertEqual(chunks, [b"valid-wav-bytes"])
        self.assertEqual(tts.request_id, "text-1")
        self.assertEqual(tts.rate_limit_headers["x-ratelimit-remaining"], "29")

    async def test_sync_tts_polls_same_job_after_documented_timeout(self) -> None:
        api = FakeHTTPClient(
            post_responses=[
                httpx.Response(
                    503,
                    json={"data": {"text_id": "text-2"}, "status": "Error"},
                )
            ],
            get_responses=[
                httpx.Response(
                    200,
                    json={
                        "status": "Ok",
                        "data": {
                            "processing_status": "TTS_TEXT_AUDIO_GENERATED",
                            "audio_path": "https://audio.example/recovered.wav",
                        },
                    },
                )
            ],
        )
        download = FakeHTTPClient(
            get_responses=[httpx.Response(200, content=b"recovered-wav")]
        )
        with patch(
            "faultbridge.adapters.sahara.httpx.AsyncClient",
            side_effect=[api, download],
        ):
            tts = SaharaSynchronousTTS(api_key="test-key", poll_interval_seconds=0.01)
            chunks = [
                chunk
                async for chunk in tts.synthesize(
                    "Network no dey work today.",
                    language="pcm",
                    accent="pidgin",
                )
            ]

        self.assertEqual(
            api.gets[0][0],
            "https://infer.voice.intron.io/tts/v1/status/text-2",
        )
        self.assertEqual(chunks, [b"recovered-wav"])

    async def test_tts_rejects_an_empty_language(self) -> None:
        generator = SaharaStreamingTTS(api_key="test-key").synthesize(
            "We found the verified network fault.",
            language=" ",
            accent="pidgin",
        )
        with self.assertRaisesRegex(ValueError, "language is required"):
            await anext(generator)

    async def test_tts_rejects_an_empty_accent_before_connecting(self) -> None:
        generator = SaharaStreamingTTS(api_key="test-key").synthesize(
            "We found the verified network fault.",
            language="pcm",
            accent=" ",
        )
        with self.assertRaisesRegex(ValueError, "accent is required"):
            await anext(generator)

    async def test_tts_rejects_mismatched_chunk_acknowledgement(self) -> None:
        socket = FakeSocket(
            received=[
                {"message_type": "SESSION_CREATED"},
                {"message_type": "TEXT_CHUNK_ACK", "chunk_id": 2},
            ]
        )
        with patch(
            "faultbridge.adapters.sahara.websockets.connect", return_value=socket
        ):
            generator = SaharaStreamingTTS(api_key="test-key").synthesize(
                "We found the verified network fault.",
                language="pcm",
                accent="pidgin",
            )
            with self.assertRaisesRegex(SaharaError, "unexpected text chunk"):
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
