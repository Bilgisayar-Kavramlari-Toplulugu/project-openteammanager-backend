from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Veritabanı bağlantısı
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,       # Minimum açık bağlantı sayısı
    max_overflow=15,   # Ekstra açılabilecek bağlantı sayısı
    echo=settings.APP_ENV == "development",  # Geliştirmede SQL sorgularını logla
)

# Her istek için ayrı session oluşturan fabrika
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Tüm modeller bu sınıftan miras alacak
class Base(DeclarativeBase):
    pass