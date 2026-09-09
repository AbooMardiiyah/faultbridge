from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol


class SpeechToText(Protocol):
    async def transcribe(self, pcm16_audio: bytes, *, language_pair: str) -> str: ...


class TextToSpeech(Protocol):
    async def synthesize(
        self, text: str, *, language: str, accent: str
    ) -> AsyncIterator[bytes]: ...
