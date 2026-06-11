from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    agent_api_key: str = Field(alias="AGENT_API_KEY")
    agent_base_url: str = Field(alias="AGENT_BASE_URL")
    agent_model: str = Field(alias="AGENT_MODEL")
    mongodb_uri: str = Field(default="", alias="MONGODB_URI")
    mongo_db: str = Field(default="brand_intel", alias="MONGO_DB")
    webhook_token: str = Field(alias="WEBHOOK_TOKEN")
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")

    # Repository backend selection:
    #   "mongo" (default) — kết nối Mongo trực tiếp qua PyMongo (dev/VM local).
    #   "http"            — gọi data-backend qua HTTP (runtime PUBLIC trên AgentBase,
    #                        không chạm Mongo trực tiếp; đi qua Cloudflare tunnel).
    repo_mode: str = Field(default="mongo", alias="REPO_MODE")
    data_backend_url: str = Field(default="", alias="DATA_BACKEND_URL")
    data_backend_token: str = Field(default="", alias="DATA_BACKEND_TOKEN")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
