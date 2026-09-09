from __future__ import annotations

from faultbridge.adapters.base import (
    AgentModel,
    SpeechToText,
    TelephonyTransport,
    TextToSpeech,
)
from faultbridge.adapters.llm import OpenAICompatibleAgentModel
from faultbridge.adapters.sahara import (
    SaharaConversationCall,
    SaharaStreamingSTT,
    SaharaStreamingTTS,
)
from faultbridge.config import Settings


class ProviderConfigurationError(RuntimeError):
    pass


def _secret(value: object | None, name: str) -> str:
    if value is None:
        raise ProviderConfigurationError(f"{name} is required")
    secret = value.get_secret_value()
    if not secret:
        raise ProviderConfigurationError(f"{name} is required")
    return secret


def build_stt(settings: Settings) -> SpeechToText:
    if settings.stt_provider.lower() == "sahara":
        return SaharaStreamingSTT(
            api_key=_secret(settings.sahara_api_key, "SAHARA_API_KEY"),
            endpoint=settings.sahara_stt_ws_url,
        )
    raise ProviderConfigurationError(
        f"unsupported STT provider {settings.stt_provider!r}"
    )


def build_tts(settings: Settings) -> TextToSpeech:
    if settings.tts_provider.lower() == "sahara":
        return SaharaStreamingTTS(
            api_key=_secret(settings.sahara_api_key, "SAHARA_API_KEY"),
            endpoint=settings.sahara_tts_ws_url,
        )
    raise ProviderConfigurationError(
        f"unsupported TTS provider {settings.tts_provider!r}"
    )


def build_agent_model(settings: Settings) -> AgentModel:
    provider = settings.agent_provider.lower()
    if provider == "openai":
        api_key = _secret(settings.openai_api_key, "OPENAI_API_KEY")
        base_url = settings.openai_base_url
    elif provider == "groq":
        api_key = _secret(settings.groq_api_key, "GROQ_API_KEY")
        base_url = settings.groq_base_url
    else:
        raise ProviderConfigurationError(f"unsupported agent provider {provider!r}")
    return OpenAICompatibleAgentModel(
        api_key=api_key,
        model=settings.agent_model,
        base_url=base_url,
        timeout_seconds=settings.agent_timeout_seconds,
    )


def build_telephony(settings: Settings) -> TelephonyTransport:
    if not settings.sahara_voicebot_workflow_id:
        raise ProviderConfigurationError("SAHARA_VOICEBOT_WORKFLOW_ID is required")
    return SaharaConversationCall(
        api_key=_secret(settings.sahara_api_key, "SAHARA_API_KEY"),
        workflow_id=settings.sahara_voicebot_workflow_id,
        endpoint=settings.sahara_voicebot_url,
    )
