from __future__ import annotations

from typing import AsyncIterator, Protocol


class SpeechToText(Protocol):
    async def transcribe(self, audio: bytes, *, language_pair: str) -> str: ...


class TextToSpeech(Protocol):
    async def synthesize(
        self, text: str, *, language: str, accent: str
    ) -> AsyncIterator[bytes]: ...

