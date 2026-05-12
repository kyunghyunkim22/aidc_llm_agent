from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    maria_host: str
    maria_port: int = 3306
    maria_user: str
    maria_password: str
    maria_db: str
    maria_pool_min: int = 2
    maria_pool_max: int = 10

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8001
    # 빈 문자열이면 인증 비활성화(개발용). 운영에서는 반드시 환경변수 MCP_API_KEY 로 주입.
    mcp_api_key: str = ""

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
