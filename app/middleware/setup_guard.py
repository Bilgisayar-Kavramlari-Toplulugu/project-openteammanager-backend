from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.database import AsyncSessionLocal


# Setup kontrolünden muaf tutulan path'ler
SETUP_EXEMPT_PATHS = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
}

EXEMPT_METHODS = {"OPTIONS"}


class SetupGuardMiddleware(BaseHTTPMiddleware):
    """
    Her istekte setup_completed kontrolü yapar.
    - setup_completed = False → sadece /api/v1/setup'a izin ver, diğerlerine 503 döndür
    - setup_completed = True  → /api/v1/setup'a erişimi engelle (403)
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in EXEMPT_METHODS:
            return await call_next(request)

        path = request.url.path

        # Muaf path'lerde direkt geç
        if path in SETUP_EXEMPT_PATHS:
            return await call_next(request)

        is_setup_path = path.startswith("/api/v1/setup")

        # DB'den setup durumunu kontrol et
        setup_completed = await self._check_setup_completed(request)

        if not setup_completed:
            # Setup tamamlanmadı — sadece /api/v1/setup'a izin ver
            if not is_setup_path:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Setup Required",
                        "message": "Sistem henüz kurulmadı. Lütfen önce kurulum sihirbazını tamamlayın.",
                        "setup_url": "/api/v1/setup",
                    },
                )
        else:
            # Setup tamamlandı — /api/v1/setup'a erişimi engelle
            if is_setup_path:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Forbidden",
                        "message": "Kurulum zaten tamamlanmış.",
                    },
                )

        return await call_next(request)

    async def _check_setup_completed(self, request: Request) -> bool:
        """
        get_db override'ını kullanarak DB'den setup durumunu okur.
        Bu sayede testlerde test DB'si, production'da production DB'si kullanılır.
        """
        from app.services.setup_service import is_setup_completed
        from app.routers.auth import get_db
        from app.main import app

        try:
            # dependency_overrides varsa onu kullan (test ortamı), yoksa get_db'yi kullan
            get_db_func = app.dependency_overrides.get(get_db, get_db)
            async for db in get_db_func():
                return await is_setup_completed(db)
        except Exception:
            # DB bağlantısı yoksa setup tamamlanmamış say
            return False

        return False