from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    faultbridge_pseudonym_secret: SecretStr = Field(min_length=32)
    faultbridge_internal_api_key: SecretStr = Field(min_length=32)
    sahara_api_key: SecretStr | None = None
    sahara_stt_ws_url: str = "wss://infer.voice.intron.io/stt/v1/stream"
    sahara_tts_ws_url: str = "wss://infer.voice.intron.io/tts/v1/stream"
    sahara_voicebot_workflow_id: str | None = None
    sahara_voicebot_url: str = (
        "https://voicebot.intron.health/voicebot/v1/convobot/call"
    )
    stt_provider: str = "sahara"
    tts_provider: str = "sahara"
    agent_provider: str = "openai"
    agent_model: str = "gpt-4.1-mini"
    agent_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    assemblyai_api_key: SecretStr | None = None
    huggingface_token: SecretStr | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_phone_number: str | None = None
    compensation_webhook_url: str | None = None
    callback_webhook_url: str | None = None
    operator_webhook_token: SecretStr | None = None
    transcript_retention_days: int = Field(default=30, ge=1, le=365)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
