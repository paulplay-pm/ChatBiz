from __future__ import annotations
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(..., description="asyncpg URL to PostgreSQL")
    redis_url: str = Field(..., description="Redis URL")
    credential_service_url: str = Field(..., description="credential service base URL")
    service_token_path: str = Field(default="/var/run/chatbiz/service-token")

    pii_fail_open: bool = Field(default=True)
    pii_map_ttl_seconds: int = Field(default=1800)
    routing_table_ttl_seconds: int = Field(default=60)
    credential_cache_ttl_seconds: int = Field(default=300)
    upstream_timeout_ms: int = Field(default=30000)
    max_body_bytes: int = Field(default=1_048_576)
    alert_webhook_url: str = Field(default="http://alerts:9090/alert")
    log_level: str = Field(default="info")
    environment: str = Field(default="local")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
