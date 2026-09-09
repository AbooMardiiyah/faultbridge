from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from urllib.parse import urlencode

import websockets

LANGUAGE_CODES = {
    "english": "en",
    "hausa-english": "ha",
    "igbo-english": "ig",
    "pidgin-english": "pcm",
    "yoruba-english": "yo",
}

TERMINAL_ERRORS = {
    "ERROR",
    "INPUT_ERROR",
    "AUTHENTICATION_ERROR",
    "RESOURCE_EXHAUSTED",
    "QUOTA_EXCEEDED",
    "CHUNK_SIZE_TOO_SMALL",
    "CHUNK_SIZE_TOO_LARGE",
    "INSUFFICIENT_AUDIO_ACTIVITY",
    "SESSION_TIME_LIMIT_EXCEEDED",
    "CHUNK_ID_MISMATCH_WITH_TOTAL",
}


class SaharaError(RuntimeError):
    """Raised when Sahara rejects or cannot complete a stream."""


def language_code(language_pair: str) -> str:
    try:
        return LANGUAGE_CODES[language_pair.strip().lower()]
    except KeyError as error:
        supported = ", ".join(sorted(LANGUAGE_CODES))
        raise ValueError(
            f"unsupported Sahara language pair {language_pair!r}; use one of {supported}"
        ) from error


def pcm16_chunks(
    audio: bytes, *, target_size: int = 16 * 1024, minimum_size: int = 1024
) -> list[bytes]:
    """Split PCM16 into Sahara-compatible 1–32 KB chunks without losing samples."""
    if not audio:
        raise ValueError("PCM16 audio cannot be empty")
    if len(audio) % 2:
        raise ValueError("PCM16 audio must contain complete 16-bit samples")
    if not minimum_size <= target_size <= 32 * 1024:
        raise ValueError("target chunk size must be between 1 KB and 32 KB")

    chunks = [
        audio[index : index + target_size]
        for index in range(0, len(audio), target_size)
    ]
    if len(chunks) == 1 and len(chunks[0]) < minimum_size:
        padding = minimum_size - len(chunks[0])
        chunks[0] += bytes(padding + padding % 2)
    elif len(chunks[-1]) < minimum_size:
        chunks[-2] += chunks.pop()
    return chunks


@dataclass(frozen=True, slots=True)
class SaharaStreamingSTT:
    """Client for Sahara's PCM16 WebSocket transcription endpoint."""

    api_key: str
    endpoint: str = "wss://infer.voice.intron.io/stt/v1/stream"
    sample_rate: int = 16_000
    bit_rate: int = 16
    num_channels: int = 1
    timeout_seconds: float = 45.0

    async def transcribe(self, pcm16_audio: bytes, *, language_pair: str) -> str:
        if not self.api_key:
            raise ValueError("Sahara API key is required")
        params = urlencode(
            {
                "sample_rate": self.sample_rate,
                "bit_rate": self.bit_rate,
                "num_channels": self.num_channels,
                "use_language_asr_input": language_code(language_pair),
            }
        )
        url = f"{self.endpoint}?{params}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with asyncio.timeout(self.timeout_seconds):
            async with websockets.connect(
                url,
                additional_headers=headers,
                open_timeout=self.timeout_seconds,
                max_size=2**20,
            ) as socket:
                ready = json.loads(await socket.recv())
                self._raise_for_error(ready)
                if ready.get("message_type") != "SESSION_CREATED":
                    raise SaharaError(
                        f"expected SESSION_CREATED, received {ready.get('message_type')}"
                    )

                for ack_id, chunk in enumerate(pcm16_chunks(pcm16_audio), start=1):
                    await socket.send(
                        json.dumps(
                            {
                                "message_type": "INPUT_AUDIO_CHUNK",
                                "audio_base_64": base64.b64encode(chunk).decode(
                                    "ascii"
                                ),
                                "ack_id": ack_id,
                            }
                        )
                    )
                await socket.send(json.dumps({"message_type": "COMMIT"}))

                async for raw_message in socket:
                    message = json.loads(raw_message)
                    self._raise_for_error(message)
                    if message.get("message_type") == "COMMITTED_TRANSCRIPT":
                        transcript = message.get("transcript_text", "").strip()
                        if not transcript:
                            raise SaharaError("Sahara returned an empty transcript")
                        return transcript

        raise SaharaError("Sahara closed the stream before returning a transcript")

    @staticmethod
    def _raise_for_error(message: dict) -> None:
        message_type = message.get("message_type")
        if message_type in TERMINAL_ERRORS:
            detail = message.get("message") or message.get("status") or "unknown error"
            raise SaharaError(f"{message_type}: {detail}")
