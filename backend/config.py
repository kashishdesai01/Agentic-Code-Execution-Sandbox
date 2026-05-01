from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-6"

    redis_url: str = "redis://localhost:6379"
    session_ttl_seconds: int = 604800  # 7 days

    sandbox_image: str = "sandbox-image"
    docker_timeout_seconds: int = 10
    docker_memory: str = "128m"
    docker_cpus: str = "0.5"

    max_retries: int = 3

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
