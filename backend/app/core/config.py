from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LitScope"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    DEBUG: bool = True

    # Database configuration
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/litscope_dev"

    # Security & Authentication
    JWT_SECRET_KEY: str = "litscope-dev-jwt-secret-key-for-local-development-only-min32bytes"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Storage configuration
    LOCAL_STORAGE_PATH: str = "./data/storage"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
