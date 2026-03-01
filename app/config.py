from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AI Resume Engine"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Database — default to SQLite so local dev works without Postgres
    DATABASE_URL: str = "sqlite:///./resume.db"

    # JWT Authentication
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production-minimum-32-chars-recommended"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    BCRYPT_LOG_ROUNDS: int = 12

    # Logging
    LOG_LEVEL: str = "INFO"        # DEBUG | INFO | WARNING | ERROR
    LOG_DIR: str = "logs"          # Directory for rotating log files
    LOG_FORMAT: str = "json"       # "json" (structured) | "text" (human-readable)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
