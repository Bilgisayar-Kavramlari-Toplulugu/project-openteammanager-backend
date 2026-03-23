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
    created_at: datetime
    model_config = {"from_attributes": True}


class MemberInvite(BaseModel):
    user_id: uuid.UUID
    role: str = "member"

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ("admin", "member", "viewer"):
            raise ValueError("Geçerli roller: admin, member, viewer")
        return v


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    status: str
    joined_at: datetime | None
    model_config = {"from_attributes": True}