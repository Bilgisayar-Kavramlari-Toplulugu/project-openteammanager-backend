from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.setup import SetupRequest, SetupStatusResponse, SetupCompleteResponse
from app.services import setup_service

router = APIRouter(prefix="/api/v1/setup", tags=["setup"])


@router.get("", response_model=SetupStatusResponse)
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    """Setup tamamlandı mı kontrol eder."""
    return await setup_service.get_setup_status(db)


@router.post("", response_model=SetupCompleteResponse, status_code=201)
async def complete_setup(
    data: SetupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Owner hesabını ve organizasyonu oluşturarak setup'ı tamamlar."""
    return await setup_service.complete_setup(db, data)