from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers.auth import router as auth_router
from app.middleware.rate_limiting import RateLimiterMiddleware, InMemoryStorage
from app.routers.organizations import router as organizations_router

app = FastAPI(
    title="Open Team Manager API",
    version="0.1.0",
    docs_url="/docs",       # Swagger UI adresi
    redoc_url="/redoc",     # ReDoc adresi
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimiterMiddleware, storage=InMemoryStorage())

app.include_router(auth_router)
app.include_router(organizations_router)

@app.get("/health", tags=["System"])
async def health_check():
    """Docker ve monitoring araçları bu endpoint'i kullanır."""
    return {"status": "ok", "env": settings.APP_ENV}
