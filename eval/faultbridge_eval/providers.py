from __future__ import annotations

import asyncio
import json
import re
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

import websockets

from faultbridge.adapters.sahara import SaharaStreamingSTT


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    transcript: str
    elapsed_seconds: float
    first_partial_seconds: float | None = None
    provider_request_id: str | None = None


class BenchmarkTranscriber(Protocol):
    name: str
    model_identifier: str

    def parameters(self) -> dict[str, Any]: ...

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult: ...


def read_pcm16_wav(path: Path) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path} must be mono PCM16 WAV")
        sample_rate = source.getframerate()
        return source.readframes(source.getnframes()), sample_rate


@dataclass(frozen=True, slots=True)
class SaharaBenchmarkTranscriber:
    client: SaharaStreamingSTT
    name: str = "sahara"

    @property
    def model_identifier(self) -> str:
        return "sahara-streaming-stt@provider-default"

    def parameters(self) -> dict[str, Any]:
        return {
            "endpoint": self.client.endpoint,
            "sample_rate": self.client.sample_rate,
            "bit_rate": self.client.bit_rate,
            "num_channels": self.client.num_channels,
            "realtime_pacing": self.client.realtime_pacing,
        }

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        audio, sample_rate = read_pcm16_wav(audio_path)
        if sample_rate != self.client.sample_rate:
            raise ValueError(
                f"Sahara benchmark audio must be {self.client.sample_rate} Hz"
            )
        started = time.monotonic()
        transcript = await self.client.transcribe(audio, language_pair=language_pair)
        return TranscriptionResult(transcript, time.monotonic() - started)


@dataclass(frozen=True, slots=True)
class AssemblyAIStreamingTranscriber:
    api_key: str
    model: str = "whisper-rt"
    endpoint: str = "wss://streaming.assemblyai.com/v3/ws"
    realtime_pacing: bool = True
    chunk_milliseconds: int = 100
    timeout_seconds: float = 180.0
    name: str = "assemblyai-whisper-rt"

    @property
    def model_identifier(self) -> str:
        return self.model

    def parameters(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "realtime_pacing": self.realtime_pacing,
            "chunk_milliseconds": self.chunk_milliseconds,
        }

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        del language_pair
        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required")
        audio, sample_rate = read_pcm16_wav(audio_path)
        params = urlencode({"sample_rate": sample_rate, "speech_model": self.model})
        started = time.monotonic()
        first_partial: float | None = None
        final_turns: dict[int, str] = {}
        request_id: str | None = None
        chunk_size = sample_rate * 2 * self.chunk_milliseconds // 1000

        async with asyncio.timeout(self.timeout_seconds):
            async with websockets.connect(
                f"{self.endpoint}?{params}",
                additional_headers={"Authorization": self.api_key},
                open_timeout=self.timeout_seconds,
                max_size=8 * 2**20,
            ) as socket:
                begin = json.loads(await socket.recv())
                if begin.get("type") != "Begin":
                    raise RuntimeError(
                        f"AssemblyAI stream failed: {begin.get('error')}"
                    )
                request_id = begin.get("id")

                async def send_audio() -> None:
                    for index in range(0, len(audio), chunk_size):
                        chunk = audio[index : index + chunk_size]
                        await socket.send(chunk)
                        if self.realtime_pacing:
                            await asyncio.sleep(len(chunk) / (sample_rate * 2))
                    await socket.send(json.dumps({"type": "Terminate"}))

                sender = asyncio.create_task(send_audio())
                try:
                    async for raw_message in socket:
                        message = json.loads(raw_message)
                        if message.get("type") == "Turn":
                            transcript = str(message.get("transcript", "")).strip()
                            if transcript and first_partial is None:
                                first_partial = time.monotonic() - started
                            if message.get("end_of_turn") and transcript:
                                turn_order = int(message.get("turn_order", 0))
                                final_turns[turn_order] = transcript
                        elif message.get("type") == "Termination":
                            break
                        elif message.get("type") == "Error":
                            raise RuntimeError(
                                "AssemblyAI streaming transcription failed"
                            )
                finally:
                    await sender

        final_transcript = " ".join(final_turns[key] for key in sorted(final_turns))
        if not final_transcript:
            raise RuntimeError("AssemblyAI returned no final transcript")
        return TranscriptionResult(
            final_transcript,
            time.monotonic() - started,
            first_partial,
            request_id,
        )


class FasterWhisperTranscriber:
    name = "faster-whisper"

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: str = "benchmark/model_cache",
    ) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise RuntimeError(
                "install the benchmark extra before using Faster-Whisper"
            ) from error
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )

    @property
    def model_identifier(self) -> str:
        return self.model_name

    def parameters(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "compute_type": self.compute_type,
            "vad_filter": True,
            "realtime_pacing": False,
        }

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        del language_pair
        started = time.monotonic()

        def run() -> str:
            segments, _ = self._model.transcribe(str(audio_path), vad_filter=True)
            return " ".join(segment.text.strip() for segment in segments).strip()

        transcript = await asyncio.to_thread(run)
        if not transcript:
            raise RuntimeError("Faster-Whisper returned no transcript")
        return TranscriptionResult(transcript, time.monotonic() - started)


def _prediction_text(value: Any) -> str:
    text = value.text if hasattr(value, "text") else str(value)
    return text.strip()


class SBPNTranscriber:
    name = "sbpn-base"

    def __init__(
        self,
        model_name: str = "ogunlao/SBPN_multilingual_base",
        *,
        device: str = "cpu",
    ) -> None:
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as error:
            raise RuntimeError(
                "install the SBPN benchmark environment first"
            ) from error
        self.model_name = model_name
        self.device = device
        config = nemo_asr.models.EncDecHybridRNNTCTCBPEModel.from_pretrained(
            model_name=model_name,
            return_config=True,
        )
        # The published checkpoint requests k2's graph_rnnt training loss. Loss
        # computation is disabled for inference, but NeMo still constructs it
        # while restoring the model. Use its built-in loss to avoid requiring k2;
        # this does not alter the checkpoint weights or decoding configuration.
        config.loss.loss_name = "pytorch"
        config.loss.loss_kwargs = {}
        self._model = nemo_asr.models.EncDecHybridRNNTCTCBPEModel.from_pretrained(
            model_name=model_name,
            override_config_path=config,
        )
        self._model.to(device)
        self._model.eval()

    @property
    def model_identifier(self) -> str:
        return self.model_name

    def parameters(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "batch_size": 1,
            "language_identification": "model-generated",
            "rnnt_loss_override": "pytorch (inference only)",
            "realtime_pacing": False,
        }

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        del language_pair
        started = time.monotonic()

        def run() -> str:
            outputs = self._model.transcribe([str(audio_path)], batch_size=1)
            if not outputs:
                return ""
            return re.sub(r"<[^>]+>", "", _prediction_text(outputs[0])).strip()

        transcript = await asyncio.to_thread(run)
        if not transcript:
            raise RuntimeError("SBPN returned no transcript")
        return TranscriptionResult(transcript, time.monotonic() - started)


class OmniASRCTCTranscriber:
    name = "meta-omniasr-ctc"

    def __init__(
        self,
        model_card: str = "omniASR_CTC_300M_v2",
        *,
        device: str | None = None,
    ) -> None:
        try:
            from omnilingual_asr.models.inference.pipeline import ASRInferencePipeline
        except ImportError as error:
            raise RuntimeError(
                "install the OmniASR benchmark environment first"
            ) from error
        self.model_card = model_card
        self.device = device
        self._pipeline = ASRInferencePipeline(model_card=model_card, device=device)

    @property
    def model_identifier(self) -> str:
        return self.model_card

    def parameters(self) -> dict[str, Any]:
        return {
            "device": self.device or "auto",
            "batch_size": 1,
            "language_conditioning": False,
            "realtime_pacing": False,
        }

    async def transcribe(
        self, audio_path: Path, *, language_pair: str
    ) -> TranscriptionResult:
        del language_pair
        started = time.monotonic()

        def run() -> str:
            outputs = self._pipeline.transcribe([str(audio_path)], batch_size=1)
            return _prediction_text(outputs[0]) if outputs else ""

        transcript = await asyncio.to_thread(run)
        if not transcript:
            raise RuntimeError("Meta OmniASR returned no transcript")
        return TranscriptionResult(transcript, time.monotonic() - started)
