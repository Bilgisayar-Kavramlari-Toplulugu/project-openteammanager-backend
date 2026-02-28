from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

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


@app.get("/health", tags=["System"])
async def health_check():
    """Docker ve monitoring araçları bu endpoint'i kullanır."""
    return {"status": "ok", "env": settings.APP_ENV}
