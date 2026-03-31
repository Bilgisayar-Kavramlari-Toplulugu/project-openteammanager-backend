import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from app.models.task import Task
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.schemas.task import TaskCreate, TaskUpdate, TaskMoveRequest

POSITION_GAP = 1000.0
REBALANCE_THRESHOLD = 0.001


async def create_task(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, data: TaskCreate, user_id: uuid.UUID) -> Task:
    await _require_project_member(db, project_id, user_id)

    # task_number otomatik artır
    result = await db.execute(
        select(func.max(Task.task_number)).where(Task.project_id == project_id)
    )
    max_number = result.scalar() or 0
    task_number = max_number + 1

    # position hesapla — aynı status'taki en son görevin sonuna ekle
    result = await db.execute(
        select(func.max(Task.position)).where(
            Task.project_id == project_id,
            Task.status == data.status,
            Task.deleted_at.is_(None),
        )
    )
    max_position = result.scalar() or 0.0
    position = max_position + POSITION_GAP

    task = Task(
        project_id=project_id,
        parent_id=data.parent_id,
        title=data.title,
        description=data.description,
        task_number=task_number,
        status=data.status,
        priority=data.priority,
        task_type=data.task_type,
        assignee_id=data.assignee_id,
        reporter_id=user_id,
        due_date=data.due_date,
        start_date=data.start_date,
        estimated_hours=data.estimated_hours,
        story_points=data.story_points,
        labels=data.labels,
        position=position,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_tasks(
    db: AsyncSession,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str | None = None,
    assignee_id: uuid.UUID | None = None,
    label: str | None = None,
) -> list[Task]:
    await _require_project_member(db, project_id, user_id)

    query = select(Task).where(
        Task.project_id == project_id,
        Task.deleted_at.is_(None),
    )
    if status:
        query = query.where(Task.status == status)
    if assignee_id:
        query = query.where(Task.assignee_id == assignee_id)
    if label:
        query = query.where(Task.labels.any(label))

    query = query.order_by(Task.status, Task.position)
    result = await db.execute(query)
    return result.scalars().all()


async def get_task(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
    await _require_project_member(db, project_id, user_id)
    return await _get_task_or_404(db, project_id, task_id)


async def update_task(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate, user_id: uuid.UUID) -> Task:
    await _require_project_member(db, project_id, user_id)
    task = await _get_task_or_404(db, project_id, task_id)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(task, field, value)

    if data.status == "done" and not task.completed_at:
        task.completed_at = datetime.now(timezone.utc)
    elif data.status and data.status != "done":
        task.completed_at = None

    await db.commit()
    await db.refresh(task)
    return task


async def move_task(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, data: TaskMoveRequest, user_id: uuid.UUID) -> Task:
    await _require_project_member(db, project_id, user_id)
    task = await _get_task_or_404(db, project_id, task_id)

    task.status = data.status
    task.position = data.position

    if data.status == "done" and not task.completed_at:
        task.completed_at = datetime.now(timezone.utc)
    elif data.status != "done":
        task.completed_at = None

    # Rebalance gerekiyor mu kontrol et
    await _rebalance_if_needed(db, project_id, data.status)

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, user_id: uuid.UUID):
    await _require_project_member(db, project_id, user_id)
    task = await _get_task_or_404(db, project_id, task_id)
    task.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# --- Yardımcı fonksiyonlar ---

async def _get_task_or_404(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.project_id == project_id,
            Task.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    return task


async def _require_project_member(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID):
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu projeye erişim yetkiniz yok")


async def _rebalance_if_needed(db: AsyncSession, project_id: uuid.UUID, status: str):
    result = await db.execute(
        select(Task).where(
            Task.project_id == project_id,
            Task.status == status,
            Task.deleted_at.is_(None),
        ).order_by(Task.position)
    )
    tasks = result.scalars().all()

    # Ardışık iki görev arasındaki fark threshold'un altına düştüyse rebalance yap
    needs_rebalance = any(
        tasks[i + 1].position - tasks[i].position < REBALANCE_THRESHOLD
        for i in range(len(tasks) - 1)
    )

    if needs_rebalance:
        for i, task in enumerate(tasks):
            task.position = (i + 1) * POSITION_GAP