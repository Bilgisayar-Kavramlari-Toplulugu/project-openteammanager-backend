import uuid
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.activity_log import ActivityLog


async def require_project_member(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Kullanıcı proje üyesi değilse 403 fırlatır."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu projeye erişim yetkiniz yok!")


async def is_project_manager(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Kullanıcının proje yöneticisi olup olmadığını döner."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role.in_(["manager", "owner"]),
        )
    )
    return result.scalar_one_or_none() is not None


async def get_task_or_404(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    """Task yoksa veya silinmişse 404 fırlatır.
    assignee ve reporter selectinload ile yüklenir —
    lazy="raise" olduğu için explicit yükleme zorunlu.
    """
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.reporter))
        .where(
            Task.id == task_id,
            Task.project_id == project_id,
            Task.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    return task


async def log_activity(db: AsyncSession, *, org_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID | None, actor_id: uuid.UUID, action: str, entity_type: str, entity_id: uuid.UUID) -> None:
    """Activity log kaydı oluşturur.
      entity_type çağıran service tarafından belirlenir: "comment", "attachment" vb.
    """
    log = ActivityLog(
        organization_id=org_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(log)