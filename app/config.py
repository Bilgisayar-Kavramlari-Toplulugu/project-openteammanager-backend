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

    # Storage
    STORAGE_BACKEND: str = "minio"
    STORAGE_BUCKET: str = "otm-files"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    AWS_ACCESS_KEY_ID: str = ""         # prod'da doldurulacak, şuan zorunlu değil
    AWS_SECRET_ACCESS_KEY: str = ""     # prod'da doldurulacak, şuan zorunlu değil
    AWS_REGION: str = "eu-central-1"

    class Config:
        env_file = "/app/.env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()