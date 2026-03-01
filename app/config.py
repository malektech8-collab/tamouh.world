import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "AI Resume Engine"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Redis / Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/resume_db")

    class Config:
        env_file = ".env"

settings = Settings()
