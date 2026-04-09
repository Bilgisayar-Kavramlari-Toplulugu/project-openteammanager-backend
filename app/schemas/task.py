import uuid
from datetime import datetime, date
from pydantic import BaseModel


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "todo"
    priority: str = "medium"
    task_type: str = "task"
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    start_date: date | None = None
    estimated_hours: float | None = None
    story_points: int | None = None
    labels: list[str] = []
    parent_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    task_type: str | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    start_date: date | None = None
    estimated_hours: float | None = None
    story_points: int | None = None
    labels: list[str] | None = None


class TaskMoveRequest(BaseModel):
    status: str
    position: float


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    description: str | None
    task_number: int
    status: str
    priority: str
    task_type: str
    assignee_id: uuid.UUID | None
    reporter_id: uuid.UUID
    due_date: datetime | None
    start_date: date | None
    estimated_hours: float | None
    logged_hours: float
    story_points: int | None
    position: float
    completed_at: datetime | None
    labels: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}