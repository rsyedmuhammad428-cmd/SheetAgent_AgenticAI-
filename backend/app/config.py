from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class Settings(BaseSettings):
    gemini_api_key: str = "missing"
    gemini_model: str = "gemini-1.5-flash"
    
    openrouter_api_key: str = "missing"
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"

    database_url: str = "sqlite+aiosqlite:///./sheetagent.db"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-secret-change-in-production"
    access_token_expire_minutes: int = 1440
    cors_origins: list[str] = ["*"]

    workspace_path: Path = Path("/app/workspace")
    log_level: str = "INFO"
    environment: str = "development"

    rate_limit_per_minute: int = 30
    max_file_size_mb: int = 50

    sentry_dsn: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("database_url")
    @classmethod
    def fix_db_url(cls, v: str) -> str:
        value = v.strip()

        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)

        if not value.startswith("postgresql+asyncpg://"):
            return value

        parts = urlsplit(value)
        normalized_query = []
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True):
            lowered_key = key.lower()
            if lowered_key == "sslmode":
                normalized_query.append(("ssl", query_value))
            elif lowered_key == "channel_binding":
                continue
            else:
                normalized_query.append((key, query_value))

        return urlunsplit(parts._replace(query=urlencode(normalized_query)))

    @field_validator("redis_url")
    @classmethod
    def fix_redis_url(cls, v: str) -> str:
        value = v.strip()

        if value.startswith("redis-cli"):
            _, _, candidate = value.partition("-u")
            value = candidate.strip() or value

        if "upstash.io" in value and value.startswith("redis://"):
            value = value.replace("redis://", "rediss://", 1)

        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def get_workspace_subdir(self, name: str) -> Path:
        p = self.workspace_path / name
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
