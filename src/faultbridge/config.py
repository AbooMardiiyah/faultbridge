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
    openai_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    assemblyai_api_key: SecretStr | None = None
    huggingface_token: SecretStr | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_phone_number: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
