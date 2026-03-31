import uuid
from datetime import datetime, date
from pydantic import BaseModel, field_validator


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    key: str
    status: str = "active"
    visibility: str = "private"
    category: str | None = None
    color: str = "#4F46E5"
    icon: str | None = None
    stack: list[str] = []
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("key")
    @classmethod
    def key_must_be_valid(cls, v):
        if not v.isupper() or not v.isalpha() or len(v) > 10:
            raise ValueError("Key yalnızca büyük harf içermeli ve 10 karakterden kısa olmalı")
        return v

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        if v not in ("planning", "active", "on_hold", "completed", "archived"):
            raise ValueError("Geçersiz 'status' bilgisi")
        return v

    @field_validator("visibility")
    @classmethod
    def visibility_must_be_valid(cls, v):
        if v not in ("private", "internal", "public"):
            raise ValueError("Geçersiz visibility")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    visibility: str | None = None
    category: str | None = None
    color: str | None = None
    icon: str | None = None
    stack: list[str] = []
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v):
        if v and v not in ("planning", "active", "on_hold", "completed", "archived"):
            raise ValueError("Geçersiz 'status' bilgisi")
        return v


class ProjectResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    key: str
    status: str
    visibility: str
    category: str | None
    color: str
    icon: str | None
    stack: list[str] = []
    is_member: bool = False
    start_date: date | None
    end_date: date | None
    created_by: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ProjectMemberInvite(BaseModel):
    user_id: uuid.UUID
    role: str = "contributor"

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v):
        if v not in ("manager", "contributor", "reviewer", "viewer"):
            raise ValueError("Geçerli roller: manager, contributor, reviewer, viewer")
        return v


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}