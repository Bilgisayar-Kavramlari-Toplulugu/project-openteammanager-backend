from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Veritabanı
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Uygulama
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = "/app/.env"
        case_sensitive = True


settings = Settings()