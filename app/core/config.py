from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "VOXAORA"
    APP_ENV: str = "development"
    ENVIRONMENT: str = "development"
    APP_SECRET_KEY: str = "dev-secret-change-in-production"
    SECRET_KEY: str = ""
    APP_ALGORITHM: str = "HS256"
    ALGORITHM: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    DATABASE_URL: str = "postgresql+asyncpg://voxaora:voxaora_pass@localhost:5432/voxaora_db"
    DATABASE_SYNC_URL: str = "postgresql://voxaora:voxaora_pass@localhost:5432/voxaora_db"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    PICOVOICE_ACCESS_KEY: str = ""

    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "voxaora-assets"
    S3_REGION: str = "us-east-1"

    PAYMENT_PROVIDER: str = "mock"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    FCM_SERVER_KEY: str = ""

    DEFAULT_CITY: str = "Riyadh"
    DEFAULT_COUNTRY: str = "SA"
    DEFAULT_CURRENCY: str = "SAR"
    DEFAULT_LANGUAGE: str = "ar"

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:3003,https://voxaora-frontend.vercel.app,https://voxaora-frontend-visiss-projects.vercel.app"

    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    @property
    def effective_secret_key(self) -> str:
        return self.SECRET_KEY or self.APP_SECRET_KEY

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
