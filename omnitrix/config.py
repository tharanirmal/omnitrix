"""Settings, read from the environment (prefix OMNITRIX_) and a local .env file."""
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMNITRIX_", env_file=".env", extra="ignore")

    database_url: str = "postgresql://omnitrix:omnitrix@localhost:5432/omnitrix"

    ollama_url: str = "http://localhost:11434"
    model_main: str = "qwen3:14b"   # planning, writing, analysis, negotiation
    model_fast: str = "qwen3:4b"    # extraction, classification, quick checks
    model_embed: str = "bge-m3"
    embed_dim: int = 1024           # must match model_embed and migrations/001_init.sql
    llm_think: bool = False
    llm_num_ctx: int = 16384
    llm_concurrency: int = 1
    llm_timeout_s: float = 180.0
    llm_keep_alive: str = "30m"     # keep all three models loaded; swapping is slow

    mailpit_url: str = "http://localhost:8025"
    mailpit_smtp_port: int = 1025
    ntfy_url: str = "http://localhost:8080"
    dashboard_port: int = 8000      # `omnitrix dashboard` - always bound to 127.0.0.1

    timezone: str = "Asia/Kolkata"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def model_for(self, role: str) -> str:
        return {"main": self.model_main, "fast": self.model_fast, "embed": self.model_embed}[role]


@lru_cache
def get_settings() -> Settings:
    return Settings()
