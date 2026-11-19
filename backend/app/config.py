from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./shopassist.db"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    DEFAULT_PROVIDER: str = "gemini"
    GUARDRAILS_ENABLED: bool = True
    PROMPT_VERSION: str = "v2_guarded"
    MAX_TOOL_STEPS: int = 6
    PENDING_ACTION_TIMEOUT_MINUTES: int = 10
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
