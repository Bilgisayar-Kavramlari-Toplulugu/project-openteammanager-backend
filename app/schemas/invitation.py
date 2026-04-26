import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


ORG_ROLES = {"owner", "member"}
PROJECT_ROLES = {"manager", "contributor", "reviewer", "viewer"}

# ── Nested kullanıcı bilgisi (response'larda kullanılır)

class InvitedUserInfo(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    email: str
    avatar_url: str | None
    model_config = {"from_attributes": True}

# ── Org Daveti

class OrgInviteCreate(BaseModel):
    invited_user_id: uuid.UUID
    role: str = "member"

    @field_validator("role")
    @classmethod
    def validate_org_role(cls, v: str) -> str:
        if v not in ORG_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(ORG_ROLES)}")
        return v


class ProjectInviteCreate(BaseModel):
    invited_user_id: uuid.UUID
    role: str = "contributor"

    @field_validator("role")
    @classmethod
    def validate_project_role(cls, v: str) -> str:
        if v not in PROJECT_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(PROJECT_ROLES)}")
        return v


class InvitationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    invited_by: uuid.UUID
    invited_user: InvitedUserInfo  # selectinload ile yüklenen relationship
    role: str
    status: str
    invite_method: str
    created_at: datetime
    responded_at: datetime | None
    model_config = {"from_attributes": True}


# ── Invite Link

class InviteLinkCreate(BaseModel):
    role: str = "member"
    expires_in_hours: int = 72

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ORG_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(ORG_ROLES)}")
        return v

    @field_validator("expires_in_hours")
    @classmethod
    def validate_expiry(cls, v: int) -> int:
        if not (1 <= v <= 720):  # maks 30 gün
            raise ValueError("expires_in_hours 1 ile 720 arasında olmalıdır")
        return v


class InviteLinkResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    token: str
    join_url: str   # service katmanında üretilir
    role: str
    expires_at: datetime
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class InviteLinkJoin(BaseModel):
    token: str


# ── Domain Allowlist

class DomainCreate(BaseModel):
    domain: str
    auto_role: str = "member"

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or "." not in v or "@" in v:
            raise ValueError("Geçersiz domain formatı. Örnek: company.com")
        return v

    @field_validator("auto_role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ORG_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(ORG_ROLES)}")
        return v


class DomainResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    domain: str
    auto_role: str
    created_at: datetime
    model_config = {"from_attributes": True}