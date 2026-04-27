import uuid
from pydantic import BaseModel, field_validator


ORG_ROLES = {"owner", "member"}
PROJECT_ROLES = {"manager", "contributor", "reviewer", "viewer"}


class OrgRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ORG_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(ORG_ROLES)}")
        return v


class ProjectRoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in PROJECT_ROLES:
            raise ValueError(f"Geçersiz rol. Geçerli değerler: {', '.join(PROJECT_ROLES)}")
        return v


class OrgMemberRoleResponse(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str

    model_config = {"from_attributes": True}


class ProjectMemberRoleResponse(BaseModel):
    user_id: uuid.UUID
    project_id: uuid.UUID
    role: str

    model_config = {"from_attributes": True}