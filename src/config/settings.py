"""
应用配置管理
- 提供 Settings 对象（FastAPI 依赖注入用）
- 支持从环境变量加载
"""

from __future__ import annotations
from pydantic import BaseSettings

class Settings(BaseSettings):
    debug: bool = False
    env: str = "dev"

    # LangSmith（可选）
    langsmith_tracing_v2: bool = True
    langsmith_api_key: str | None = None
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str = "MQoL-Dev"

    # Postgres
    database_url: str = "postgresql+psycopg://user:password@localhost:5432/psyllm"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

_settings: Settings | None = None
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings