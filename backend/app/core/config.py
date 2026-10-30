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

    # LLM & Generation Configuration
    LLM_PROVIDER: str = "auto"  # auto, ollama, gemini, groq, openai, extractive
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3:latest"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    GROQ_API_KEY: str | None = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Scholarly Discovery (Scopus / Elsevier)
    ELSEVIER_API_KEY: str | None = None
    ELSEVIER_INST_TOKEN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
