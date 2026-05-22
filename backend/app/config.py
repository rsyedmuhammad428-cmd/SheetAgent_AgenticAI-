from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    gemini_api_key: str = "missing"
    gemini_model: str = "gemini-1.5-flash"

    database_url: str = "sqlite+aiosqlite:///./sheetagent.db"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-secret-change-in-production"
    access_token_expire_minutes: int = 1440

    workspace_path: Path = Path("/app/workspace")
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:80", "http://localhost"]
    log_level: str = "INFO"
    environment: str = "development"

    rate_limit_per_minute: int = 30
    max_file_size_mb: int = 50

    sentry_dsn: Optional[str] = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @field_validator("database_url")
    @classmethod
    def fix_db_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

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
