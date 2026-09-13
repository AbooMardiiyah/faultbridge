from __future__ import annotations

from dataclasses import asdict

from faultbridge.adapters.base import (
    AgentModel,
    ComplaintAnalysis,
    SpeechToText,
    TextToSpeech,
    VoiceTurnResult,
)
from faultbridge.domain.orchestrator import FaultBridgeOrchestrator
from faultbridge.services.privacy import redact_text


class VoicePipeline:
    """Provider-neutral audio turn pipeline with a policy-controlled agent core."""

    def __init__(
        self,
        *,
        stt: SpeechToText,
        tts: TextToSpeech,
        agent_model: AgentModel,
        orchestrator: FaultBridgeOrchestrator,
    ) -> None:
        self.stt = stt
        self.tts = tts
        self.agent_model = agent_model
        self.orchestrator = orchestrator

    async def start_call(
        self,
        *,
        pcm16_audio: bytes,
        caller_id: str,
        area: str,
        cell_id: str,
        default_language_pair: str,
        consent: bool,
        voice_language: str,
        voice_accent: str,
    ) -> VoiceTurnResult:
        if consent:
            raw_transcript = await self.stt.transcribe(
                pcm16_audio, language_pair=default_language_pair
            )
            transcript = redact_text(raw_transcript)
            analysis = await self.agent_model.analyze_complaint(
                transcript, default_language_pair=default_language_pair
            )
        else:
            transcript = ""
            analysis = ComplaintAnalysis(
                symptom="unknown",
                language_pair=default_language_pair,
                consent=False,
            )
        session = self.orchestrator.start_call(
            caller_id=caller_id,
            transcript=transcript,
            area=area,
            cell_id=cell_id,
            language_pair=analysis.language_pair,
            symptom=analysis.symptom,
            consent=consent,
        )
        audio_chunks: list[bytes] = []
        async for chunk in self.tts.synthesize(
            session.response,
            language=voice_language,
            accent=voice_accent,
        ):
            audio_chunks.append(chunk)
        return VoiceTurnResult(
            transcript=transcript,
            response_text=session.response,
            response_audio_chunks=tuple(audio_chunks),
            call=asdict(session),
        )

    async def verify_call(
        self,
        *,
        pcm16_audio: bytes,
        call_id: str,
        language_pair: str,
        voice_language: str,
        voice_accent: str,
    ) -> VoiceTurnResult:
        raw_transcript = await self.stt.transcribe(
            pcm16_audio, language_pair=language_pair
        )
        transcript = redact_text(raw_transcript)
        resolved = await self.agent_model.confirms_resolution(transcript)
        session = self.orchestrator.tools.database.get_session(call_id)
        if session is None:
            raise KeyError(call_id)
        session = self.orchestrator.verify_resolution(session, resolved=resolved)
        audio_chunks: list[bytes] = []
        async for chunk in self.tts.synthesize(
            session.response,
            language=voice_language,
            accent=voice_accent,
        ):
            audio_chunks.append(chunk)
        return VoiceTurnResult(
            transcript=transcript,
            response_text=session.response,
            response_audio_chunks=tuple(audio_chunks),
            call=asdict(session),
        )
