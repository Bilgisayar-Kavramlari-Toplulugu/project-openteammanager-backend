import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator


class CommentCreate(BaseModel):
    content: str
    parent_id: uuid.UUID | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Yorum içeriği boş olamaz")
        return v.strip()


class CommentUpdate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Yorum içeriği boş olamaz")
        return v.strip()


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    parent_id: uuid.UUID | None
    content: str | None       # silinmişse None
    is_deleted: bool
    is_edited: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, comment) -> "CommentResponse":
        return cls(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            parent_id=comment.parent_id,
            content=None if comment.deleted_at else comment.content,
            is_deleted=comment.deleted_at is not None,
            is_edited=comment.is_edited,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )

    model_config = {"from_attributes": True}


class PaginatedComments(BaseModel):
    items: list[CommentResponse]
    total: int
    page: int
    limit: int
    has_next: bool