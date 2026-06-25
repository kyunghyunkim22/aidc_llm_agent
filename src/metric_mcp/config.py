from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    druid_url: str
    druid_sql_path: str = "/druid/v2/sql"
    druid_user: str = ""
    druid_password: str = ""
    druid_timeout_sec: float = 10.0

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8003
    # 빈 문자열이면 인증 비활성화(개발용). 운영에서는 반드시 환경변수 MCP_API_KEY 로 주입.
    mcp_api_key: str = ""

    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
