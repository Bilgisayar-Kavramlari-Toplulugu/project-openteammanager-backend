import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator
import re


class OrganizationCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v):
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug yalnızca küçük harf, rakam ve tire içerebilir")
        return v


class OrganizationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    owner_id: uuid.UUID
    plan: str
    org_type: str | None  # setup wizard'dan geliyor
    invite_method: str  # email | invite_link | domain_allowlist
    is_member: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class MemberInvite(BaseModel):
    user_id: uuid.UUID
    role: str = "member"

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ["member"]:
            raise ValueError("Geçerli rol: member")
        return v


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    joined_at: datetime | None
    model_config = {"from_attributes": True}


# ── Üye listeleme

class MemberUserInfo(BaseModel):
    """Üye listesinde kullanıcı bilgileri."""
    id: uuid.UUID
    username: str
    full_name: str
    avatar_url: str | None = None
    email: str
    model_config = {"from_attributes": True}


class MemberListItem(BaseModel):
    """Üye listesi için tek satır."""
    id: uuid.UUID  # organization_members.id
    user_id: uuid.UUID
    role: str  # owner | member
    status: str
    joined_at: datetime | None
    user: MemberUserInfo
    model_config = {"from_attributes": True}


class PaginatedMembers(BaseModel):
    items: list[MemberListItem]
    total: int
    page: int
    limit: int
    has_next: bool


# ── Üye profil detayı

class MemberProjectInfo(BaseModel):
    """Üyenin katıldığı proje özeti."""
    id: uuid.UUID
    name: str
    key: str
    status: str
    role: str  # projedeki rolü
    model_config = {"from_attributes": True}


class ActivityFeedItem(BaseModel):
    """Son aktivite özeti."""
    action: str
    entity_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


class MemberStats(BaseModel):
    """Üye istatistikleri."""
    total_projects: int
    total_tasks: int
    completed_tasks: int


class MemberDetailResponse(BaseModel):
    """Üye profil detayı."""
    id: uuid.UUID
    username: str
    full_name: str
    avatar_url: str | None = None
    email: str
    timezone: str
    is_active: bool
    joined_at: datetime | None  # org'a katılım tarihi
    org_role: str  # org'daki rolü: owner | member
    stats: MemberStats
    projects: list[MemberProjectInfo]
    recent_activity: list[ActivityFeedItem]
    model_config = {"from_attributes": True}