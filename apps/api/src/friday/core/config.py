from functools import lru_cache

from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"), env_prefix="FRIDAY_", extra="ignore"
    )

    env: str = "development"
    database_url: str = "postgresql+asyncpg://friday:friday@localhost:55432/friday"
    redis_url: str = "redis://localhost:6379/0"
    persistence_backend: str = "memory"
    local_user_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    model_default: str = "provider-default"
    model_realtime: str = "gpt-realtime-2.1"
    allow_external_writes: bool = False
    require_local_session: bool = False
    enable_model_calls: bool = False
    authorized_file_roots: str = "."
    allowed_browser_domains: str = "linkedin.com,github.com"
    browser_headless: bool = False
    user_display_name: str = "User"
    github_owner: str = ""
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    linkedin_client_id: str | None = None
    linkedin_client_secret: SecretStr | None = None
    linkedin_redirect_uri: str = "http://127.0.0.1:8000/v1/oauth/linkedin/callback"
    linkedin_author_urn: str | None = None
    spotify_client_id: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/v1/oauth/spotify/callback"
    gmail_client_id: str = ""
    gmail_redirect_uri: str = "http://127.0.0.1:8000/v1/oauth/gmail/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
