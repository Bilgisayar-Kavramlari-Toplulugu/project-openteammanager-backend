import re
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization
from app.models.organization_members import OrganizationMember
from app.models.user import User
from app.models.system_settings import SystemSettings
from app.schemas.setup import SetupRequest, SetupStatusResponse, SetupCompleteResponse
from app.core.security import hash_password, create_access_token, create_refresh_token


async def get_setup_status(db: AsyncSession) -> SetupStatusResponse:
    """
    Setup tamamlandı mı kontrol eder.
    - Organization kaydı yoksa → setup gerekli
    - setup_completed=True ise → 403
    """
    settings = await _get_system_settings(db)

    if settings is None or not settings.setup_completed:
        return SetupStatusResponse(
            setup_completed=False,
            message="Kurulum henüz tamamlanmadı. Lütfen setup wizard'ı tamamlayın.",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Kurulum zaten tamamlanmış.",
    )


async def complete_setup(db: AsyncSession, data: SetupRequest) -> SetupCompleteResponse:
    """
    1. Setup daha önce tamamlandıysa 403 fırlat
    2. Slug üret / benzersizliğini kontrol et
    3. Owner kullanıcısını oluştur
    4. Organization oluştur
    5. OrganizationMember kaydı oluştur (role=owner)
    6. setup_completed=True yap
    7. Token döndür
    """
    # Daha önce tamamlandıysa engelle
    settings = await _get_system_settings(db)
    if settings and settings.setup_completed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kurulum zaten tamamlanmış.",
        )

    # Slug üret
    slug = data.slug or _generate_slug(data.org_display_name)
    slug = await _ensure_unique_slug(db, slug)

    # Email / username benzersizliği
    existing_email = await db.execute(
        select(User).where(User.email == data.owner.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kayıtlı.",
        )

    # User kontrolü
    username = data.owner.username or _generate_username(data.owner.email)
    existing_username = await db.execute(
        select(User).where(User.username == username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu kullanıcı adı zaten alınmış.",
        )

    # Owner oluştur
    owner = User(
        id=uuid.uuid4(),
        email=data.owner.email,
        username=username,
        full_name=data.owner.full_name,
        password_hash=hash_password(data.owner.password),
        is_active=True,
    )
    db.add(owner)
    await db.flush()  # owner.id için

    # Organization oluştur
    organization = Organization(
        id=uuid.uuid4(),
        name=data.org_name,
        slug=slug,
        logo_url=data.org_logo_url,
        owner_id=owner.id,
        org_type=data.org_type,
        invite_method="email"
    )
    db.add(organization)
    await db.flush()  # organization.id için

    # Owner üyeliğini oluştur
    member = OrganizationMember(
        organization_id=organization.id,
        user_id=owner.id,
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)

    # System settings güncelle veya oluştur
    if settings is None:
        settings = SystemSettings(id=1, setup_completed=True)
        db.add(settings)
    else:
        settings.setup_completed = True

    await db.commit()

    # Token üret
    access_token = create_access_token(subject=str(owner.id))
    refresh_token = create_refresh_token(subject=str(owner.id))

    return SetupCompleteResponse(
        message="Kurulum başarıyla tamamlandı.",
        access_token=access_token,
        refresh_token=refresh_token,
    )


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

async def _get_organization(db: AsyncSession) -> Organization | None:
    """Sistemdeki tek organizasyonu döner. Yoksa None."""
    result = await db.execute(
        select(Organization).where(Organization.deleted_at.is_(None)).limit(1)
    )
    return result.scalar_one_or_none()


async def is_setup_completed(db: AsyncSession) -> bool:
    """Middleware tarafından kullanılır."""
    settings = await _get_system_settings(db)
    return settings is not None and settings.setup_completed


async def _get_system_settings(db: AsyncSession) -> SystemSettings | None:
    result = await db.execute(select(SystemSettings).where(SystemSettings.id == 1))
    return result.scalar_one_or_none()


def _generate_slug(display_name: str) -> str:
    """
    org_display_name'den slug üretir.
    Örn: "Açık Ekip Yöneticisi" → "acik-ekip-yoneticisi"
    """
    slug = display_name.lower().strip()
    slug = re.sub(r"[ğ]", "g", slug)
    slug = re.sub(r"[ü]", "u", slug)
    slug = re.sub(r"[ş]", "s", slug)
    slug = re.sub(r"[ı]", "i", slug)
    slug = re.sub(r"[ö]", "o", slug)
    slug = re.sub(r"[ç]", "c", slug)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "organization"


async def _ensure_unique_slug(db: AsyncSession, slug: str) -> str:
    """
    Slug benzersiz değilse sonuna sayı ekler.
    Örn: "otm" → "otm-2" → "otm-3"
    """
    result = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if not result.scalar_one_or_none():
        return slug

    # Benzersiz olana kadar sayı ekle
    counter = 2
    while True:
        new_slug = f"{slug}-{counter}"
        result = await db.execute(
            select(Organization).where(Organization.slug == new_slug)
        )
        if not result.scalar_one_or_none():
            return new_slug
        counter += 1


def _generate_username(email: str) -> str:
    """Email'den username üretir. Örn: ahmet@test.com → ahmet"""
    return email.split("@")[0].lower().replace(".", "_")