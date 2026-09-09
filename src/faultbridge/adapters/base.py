from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ComplaintAnalysis:
    """Structured, non-authoritative facts extracted from one caller turn."""

    symptom: str
    language_pair: str
    consent: bool


@dataclass(frozen=True, slots=True)
class VoiceTurnResult:
    transcript: str
    response_text: str
    response_audio_chunks: tuple[bytes, ...]
    call: dict[str, Any]


class SpeechToText(Protocol):
    async def transcribe(self, pcm16_audio: bytes, *, language_pair: str) -> str: ...


class TextToSpeech(Protocol):
    async def synthesize(
        self, text: str, *, language: str, accent: str
    ) -> AsyncIterator[bytes]: ...


class AgentModel(Protocol):
    async def analyze_complaint(
        self, transcript: str, *, default_language_pair: str
    ) -> ComplaintAnalysis: ...

    async def confirms_resolution(self, transcript: str) -> bool: ...


class TelephonyTransport(Protocol):
    async def start_call(
        self,
        phone_number: str,
        *,
        variables: dict[str, str],
        accent: str,
        gender: str,
    ) -> dict[str, Any]: ...
