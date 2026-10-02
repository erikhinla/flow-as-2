import sys
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from live_secrets import assert_production_token
except ImportError:
    _shared = Path(__file__).resolve().parents[4] / "shared"
    if str(_shared) not in sys.path:
        sys.path.insert(0, str(_shared))
    from live_secrets import assert_production_token


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    bizbrain_env: str = "dev"
    bizbrain_api_token: str = Field(
        default="change-me",
        validation_alias=AliasChoices("OPENCLAW_API_TOKEN", "BIZBRAIN_API_TOKEN"),
    )
    bizbrain_redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("BIZBRAIN_REDIS_URL", "REDIS_URL"),
    )

    social_hub_api_origin: str = "http://localhost:8000"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-5.6-terra"
    discord_webhook_url: str = ""
    output_dir: str = "/app/runtime/reviews"
    flow_state_dir: str = "~/.openclaw/state"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
