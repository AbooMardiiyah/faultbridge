from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from faultbridge_eval.providers import OmniASRCTCTranscriber, SBPNTranscriber


class _Prediction:
    def __init__(self, text: str) -> None:
        self.text = text


class _SBPNModel:
    def transcribe(self, paths: list[str], *, batch_size: int):
        if paths != ["sample.wav"] or batch_size != 1:
            raise AssertionError("unexpected SBPN invocation")
        return [_Prediction("<|pcm|> my network no dey work")]


class _OmniPipeline:
    def transcribe(self, paths: list[str], *, batch_size: int):
        if paths != ["sample.wav"] or batch_size != 1:
            raise AssertionError("unexpected OmniASR invocation")
        return ["my network no dey work"]


class LocalBenchmarkProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_sbpn_removes_model_language_tag(self) -> None:
        provider = object.__new__(SBPNTranscriber)
        provider.model_name = "test-sbpn"
        provider.device = "cpu"
        provider._model = _SBPNModel()

        with patch(
            "faultbridge_eval.providers.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda function: function()),
        ):
            result = await provider.transcribe(
                Path("sample.wav"), language_pair="Pidgin-English"
            )

        self.assertEqual(result.transcript, "my network no dey work")

    async def test_omniasr_returns_pipeline_transcript(self) -> None:
        provider = object.__new__(OmniASRCTCTranscriber)
        provider.model_card = "test-omni"
        provider.device = None
        provider._pipeline = _OmniPipeline()

        with patch(
            "faultbridge_eval.providers.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda function: function()),
        ):
            result = await provider.transcribe(
                Path("sample.wav"), language_pair="Pidgin-English"
            )

        self.assertEqual(result.transcript, "my network no dey work")


if __name__ == "__main__":
    unittest.main()
