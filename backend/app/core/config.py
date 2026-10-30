from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "LitScope"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    DEBUG: bool = True

    # Database configuration
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/litscope_dev"

    # Storage configuration
    LOCAL_STORAGE_PATH: str = "./data/storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
