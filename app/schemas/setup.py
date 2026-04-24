from pydantic import BaseModel, field_validator, EmailStr
from typing import Literal

# Request
class OwnerCreate(BaseModel):
    full_name: str
    username: str | None = None
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Şifre en az 8 karakter olmalıdır")
        return v


class SetupRequest(BaseModel):
    org_name: str
    org_display_name: str
    slug: str | None = None          # boş gelirse org_display_name'den otomatik üretilir
    org_type: Literal["commercial", "community", "individual"]
    org_logo_url: str | None = None
    owner: OwnerCreate

    @field_validator("org_type")
    @classmethod
    def org_type_required(cls, v: str) -> str:
        if not v:
            raise ValueError("org_type zorunludur")
        return v


# Response
class SetupStatusResponse(BaseModel):
    setup_completed: bool
    message: str


class SetupCompleteResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str