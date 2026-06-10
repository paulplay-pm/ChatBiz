from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    audit_isolation_url: str
    credential_service_url: str
    knowledge_base_url: str = "http://knowledge-base:8002"
    agent_runtime_url: str = "http://agent-runtime:8003"
    workflow_engine_service_token: str
    wecom_webhook_url: str = ""
    log_level: str = "info"
    environment: str = "local"
    docker_sandbox_enabled: bool = True
    docker_socket: str = "/var/run/docker.sock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
