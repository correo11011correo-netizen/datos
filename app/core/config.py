from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Railway Env Vars
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/postgres"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Admin Security
    ADMIN_SECRET_TOKEN: str = "super-secret-admin-token"
    REGISTRATION_TOKEN: str = "dev-registration-token-2026"

    # App Config
    APP_NAME: str = "Generic-DB-Sentinel"
    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
