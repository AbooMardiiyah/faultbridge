from __future__ import annotations

import asyncio
import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx
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
    "INSUFFICIENT_TEXT_ACTIVITY",
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


@dataclass(slots=True)
class SaharaStreamingSTT:
    """Client for Sahara's PCM16 WebSocket transcription endpoint."""

    api_key: str
    endpoint: str = "wss://infer.voice.intron.io/stt/v1/stream"
    sample_rate: int = 16_000
    bit_rate: int = 16
    num_channels: int = 1
    timeout_seconds: float = 45.0
    realtime_pacing: bool = False
    credit_balance: float | int | str | None = field(default=None, init=False)

    async def transcribe(self, pcm16_audio: bytes, *, language_pair: str) -> str:
        if not self.api_key:
            raise ValueError("Sahara API key is required")
        self.credit_balance = None
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
                compression=None,
                open_timeout=self.timeout_seconds,
                max_size=2**20,
                max_queue=128,
            ) as socket:
                ready = json.loads(await socket.recv())
                self._raise_for_error(ready)
                if ready.get("message_type") != "SESSION_CREATED":
                    raise SaharaError(
                        f"expected SESSION_CREATED, received {ready.get('message_type')}"
                    )
                balance = ready.get("credit_balance")
                if isinstance(balance, (float, int, str)):
                    self.credit_balance = balance

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
                    if self.realtime_pacing:
                        bytes_per_second = (
                            self.sample_rate * self.num_channels * self.bit_rate // 8
                        )
                        await asyncio.sleep(len(chunk) / bytes_per_second)
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
            metadata = {
                key: value for key, value in message.items() if key != "message_type"
            }
            detail = (
                message.get("message")
                or message.get("status")
                or json.dumps(metadata, sort_keys=True)
                or "unknown error"
            )
            raise SaharaError(f"{message_type}: {detail}")


def text_chunks(text: str, *, maximum_size: int = 100) -> list[str]:
    """Split speech text at word boundaries for Sahara's 10–100 character limit."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) < 10:
        raise ValueError("Sahara TTS text must contain at least 10 characters")
    if maximum_size < 10 or maximum_size > 100:
        raise ValueError("maximum chunk size must be between 10 and 100")

    words = normalized.split(" ")
    if any(len(word) > maximum_size for word in words):
        raise ValueError(
            f"Sahara TTS text contains a word longer than {maximum_size} characters"
        )

    # Find a complete partition so a short tail cannot be merged into a chunk
    # beyond the provider's maximum. Prefer fewer and then fuller chunks.
    partitions: list[list[str] | None] = [None] * (len(words) + 1)
    partitions[-1] = []
    for start in range(len(words) - 1, -1, -1):
        candidates: list[list[str]] = []
        length = 0
        for end in range(start, len(words)):
            length += len(words[end]) + (1 if end > start else 0)
            if length > maximum_size:
                break
            suffix = partitions[end + 1]
            if length >= 10 and suffix is not None:
                candidates.append([" ".join(words[start : end + 1]), *suffix])
        if candidates:
            partitions[start] = min(
                candidates, key=lambda chunks: (len(chunks), -len(chunks[0]))
            )
    if partitions[0] is None:
        raise ValueError("Sahara TTS text cannot be split into 10–100 character chunks")
    return partitions[0]


@dataclass(slots=True)
class SaharaStreamingTTS:
    """Client for Sahara's documented streaming TTS WebSocket contract."""

    api_key: str
    endpoint: str = "wss://infer.voice.intron.io/tts/v1/stream"
    gender: str = "female"
    output_format: str = "wav"
    timeout_seconds: float = 60.0
    poll_interval_seconds: float = 0.2
    commit_timeout_seconds: float = 10.0
    credit_balance: float | int | str | None = field(default=None, init=False)

    async def synthesize(self, text: str, *, language: str, accent: str) -> Any:
        if not self.api_key:
            raise ValueError("Sahara API key is required")
        self.credit_balance = None
        language = language.strip()
        accent = accent.strip()
        if not language:
            raise ValueError("Sahara TTS language is required")
        if not accent:
            raise ValueError("Sahara TTS accent is required")
        if self.gender not in {"female", "male"}:
            raise ValueError("Sahara TTS gender must be female or male")
        if self.output_format not in {"wav", "opus"}:
            raise ValueError("Sahara TTS output format must be wav or opus")
        params = urlencode(
            {
                "voice_language": language,
                "voice_accent": accent,
                "voice_gender": self.gender,
                "output_audio_format": self.output_format,
            }
        )
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with asyncio.timeout(self.timeout_seconds):
            async with websockets.connect(
                f"{self.endpoint}?{params}",
                additional_headers=headers,
                compression=None,
                open_timeout=self.timeout_seconds,
                max_size=8 * 2**20,
            ) as socket:
                ready = json.loads(await socket.recv())
                SaharaStreamingSTT._raise_for_error(ready)
                if ready.get("message_type") != "SESSION_CREATED":
                    raise SaharaError("Sahara TTS did not create a session")
                balance = ready.get("credit_balance")
                if isinstance(balance, (float, int, str)):
                    self.credit_balance = balance

                chunks = text_chunks(text)
                for chunk_id, chunk in enumerate(chunks, start=1):
                    await socket.send(
                        json.dumps(
                            {
                                "message_type": "INPUT_TEXT_CHUNK",
                                "text": chunk,
                                "ack_id": chunk_id,
                            }
                        )
                    )
                    acknowledgement = json.loads(await socket.recv())
                    SaharaStreamingSTT._raise_for_error(acknowledgement)
                    if acknowledgement.get("message_type") != "TEXT_CHUNK_ACK":
                        raise SaharaError("Sahara TTS did not acknowledge text")
                    acknowledged_id = acknowledgement.get("chunk_id")
                    if acknowledged_id is not None and acknowledged_id != chunk_id:
                        raise SaharaError(
                            "Sahara TTS acknowledged an unexpected text chunk"
                        )

                for chunk_id in range(1, len(chunks) + 1):
                    while True:
                        await socket.send(
                            json.dumps(
                                {
                                    "message_type": "FETCH_AUDIO_CHUNK",
                                    "chunk_id": chunk_id,
                                }
                            )
                        )
                        message = json.loads(await socket.recv())
                        SaharaStreamingSTT._raise_for_error(message)
                        response_chunk_id = message.get("chunk_id")
                        if (
                            response_chunk_id is not None
                            and response_chunk_id != chunk_id
                        ):
                            raise SaharaError(
                                "Sahara TTS returned an unexpected audio chunk"
                            )
                        processing_status = message.get(
                            "processing_status"
                        ) or message.get("processing_staus")
                        if processing_status == "READY" and message.get(
                            "audio_base_64"
                        ):
                            try:
                                yield base64.b64decode(
                                    message["audio_base_64"], validate=True
                                )
                            except (ValueError, TypeError) as error:
                                raise SaharaError(
                                    "Sahara TTS returned invalid base64 audio"
                                ) from error
                            break
                        if processing_status not in {"PROCESSING", "PENDING"}:
                            raise SaharaError(
                                f"unexpected Sahara TTS status {processing_status!r}"
                            )
                        await asyncio.sleep(self.poll_interval_seconds)

                await socket.send(json.dumps({"message_type": "COMMIT"}))
                try:
                    async with asyncio.timeout(self.commit_timeout_seconds):
                        committed = json.loads(await socket.recv())
                except TimeoutError:
                    # FETCH_AUDIO_CHUNK with READY already guarantees complete audio.
                    # The commit response only supplies the persisted-session summary;
                    # current live sessions can omit it, so do not discard valid audio.
                    return
                SaharaStreamingSTT._raise_for_error(committed)
                if committed.get("message_type") != "COMMITTED_AUDIO":
                    raise SaharaError("Sahara TTS did not commit the audio session")


@dataclass(slots=True)
class SaharaSynchronousTTS:
    """Client for Sahara's synchronous JSON TTS endpoint."""

    api_key: str
    endpoint: str = "https://infer.voice.intron.io/tts/v1/generate"
    status_endpoint: str = "https://infer.voice.intron.io/tts/v1/status/{text_id}"
    gender: str = "female"
    output_format: str = "wav"
    request_timeout_seconds: float = 130.0
    total_timeout_seconds: float = 300.0
    poll_interval_seconds: float = 1.0
    credit_balance: float | int | str | None = field(default=None, init=False)
    request_id: str | None = field(default=None, init=False)
    rate_limit_headers: dict[str, str] = field(default_factory=dict, init=False)

    async def synthesize(self, text: str, *, language: str, accent: str) -> Any:
        normalized = re.sub(r"\s+", " ", text).strip()
        language = language.strip()
        accent = accent.strip()
        self._validate(normalized, language, accent)
        self.request_id = None
        self.rate_limit_headers = {}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "text": normalized,
            "voice_language": language,
            "voice_accent": accent,
            "voice_gender": self.gender,
            "output_audio_format": self.output_format,
        }
        timeout = httpx.Timeout(self.request_timeout_seconds)
        async with asyncio.timeout(self.total_timeout_seconds):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
                self._capture_rate_limits(response)
                payload = self._response_payload(response)
                data = self._response_data(payload)
                self.request_id = self._text_id(data, payload)
                if response.status_code == 503:
                    if not self.request_id:
                        raise SaharaError(
                            "Sahara synchronous TTS timed out without a text ID"
                        )
                    data = await self._poll_status(client, headers)
                elif response.is_error:
                    raise SaharaError(
                        "Sahara synchronous TTS failed with HTTP "
                        f"{response.status_code}: {self._message(payload)}"
                    )
                elif data.get("processing_status") != "TTS_TEXT_AUDIO_GENERATED":
                    if not self.request_id:
                        raise SaharaError(
                            "Sahara synchronous TTS returned neither audio nor a text ID"
                        )
                    data = await self._poll_status(client, headers)

            audio_url = str(data.get("audio_path") or "").strip()
            parsed = urlparse(audio_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise SaharaError(
                    "Sahara synchronous TTS returned an invalid audio URL"
                )
            # Use a separate client so the Sahara bearer token is never forwarded
            # to a presigned object-storage URL.
            async with httpx.AsyncClient(
                timeout=self.request_timeout_seconds, follow_redirects=True
            ) as download_client:
                audio_response = await download_client.get(audio_url)
            if audio_response.is_error:
                raise SaharaError(
                    "Sahara TTS audio download failed with HTTP "
                    f"{audio_response.status_code}"
                )
            if not audio_response.content:
                raise SaharaError("Sahara synchronous TTS returned empty audio")
            yield audio_response.content

    def _validate(self, text: str, language: str, accent: str) -> None:
        if not self.api_key:
            raise ValueError("Sahara API key is required")
        if not text:
            raise ValueError("Sahara TTS text is required")
        if len(text) > 4096:
            raise ValueError(
                "Sahara synchronous TTS text cannot exceed 4096 characters"
            )
        if not language:
            raise ValueError("Sahara TTS language is required")
        if not accent:
            raise ValueError("Sahara TTS accent is required")
        if self.gender not in {"female", "male"}:
            raise ValueError("Sahara TTS gender must be female or male")
        if self.output_format not in {"wav", "opus"}:
            raise ValueError("Sahara TTS output format must be wav or opus")
        if self.poll_interval_seconds <= 0:
            raise ValueError("Sahara TTS poll interval must be positive")

    def _capture_rate_limits(self, response: httpx.Response) -> None:
        for name in (
            "retry-after",
            "x-ratelimit-limit",
            "x-ratelimit-remaining",
            "x-ratelimit-reset",
        ):
            if name in response.headers:
                self.rate_limit_headers[name] = response.headers[name]

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as error:
            raise SaharaError(
                "Sahara synchronous TTS returned a non-JSON response"
            ) from error
        if not isinstance(payload, dict):
            raise SaharaError("Sahara synchronous TTS returned invalid JSON")
        return payload

    @staticmethod
    def _response_data(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _text_id(data: dict[str, Any], payload: dict[str, Any]) -> str | None:
        value = data.get("text_id") or payload.get("text_id")
        return str(value) if value else None

    @staticmethod
    def _message(payload: dict[str, Any]) -> str:
        value = payload.get("message") or payload.get("status") or "unknown error"
        return str(value)

    async def _poll_status(
        self, client: httpx.AsyncClient, headers: dict[str, str]
    ) -> dict[str, Any]:
        assert self.request_id is not None
        status_url = self.status_endpoint.format(text_id=self.request_id)
        while True:
            response = await client.get(status_url, headers=headers)
            self._capture_rate_limits(response)
            payload = self._response_payload(response)
            if response.is_error:
                raise SaharaError(
                    "Sahara TTS status failed with HTTP "
                    f"{response.status_code}: {self._message(payload)}"
                )
            data = self._response_data(payload)
            status = data.get("processing_status")
            if status == "TTS_TEXT_AUDIO_GENERATED":
                return data
            if status == "TTS_TEXT_AUDIO_PROCESSING_FAILED":
                raise SaharaError("Sahara TTS processing failed")
            if status not in {
                "TTS_TEXT_AUDIO_QUEUED",
                "TTS_TEXT_AUDIO_PENDING",
                "TTS_TEXT_AUDIO_PROCESSING",
            }:
                raise SaharaError(f"unexpected Sahara TTS status {status!r}")
            await asyncio.sleep(self.poll_interval_seconds)


@dataclass(frozen=True, slots=True)
class SaharaConversationCall:
    """Launch an active Sahara Conversation workflow as an outbound call."""

    api_key: str
    workflow_id: str
    endpoint: str = "https://voicebot.intron.health/voicebot/v1/convobot/call"
    timeout_seconds: float = 30.0

    async def start_call(
        self,
        phone_number: str,
        *,
        variables: dict[str, str],
        accent: str = "pidgin",
        gender: str = "female",
    ) -> dict[str, Any]:
        if not self.api_key or not self.workflow_id:
            raise ValueError("Sahara API key and conversation workflow ID are required")
        workflow_parameters = {**variables, "phone_number": phone_number}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "workflow_id": self.workflow_id,
                    "workflow_params": [workflow_parameters],
                    "tts_voice_accent": accent,
                    "tts_voice_gender": gender,
                },
            )
        if response.is_error:
            raise SaharaError(
                f"Sahara Conversation Call failed with HTTP {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise SaharaError("Sahara Conversation Call returned an invalid response")
        return payload
