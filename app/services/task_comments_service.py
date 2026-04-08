import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_comment import TaskComment
from app.models.task import Task
from app.models.project_member import ProjectMember
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.schemas.task_comments import CommentCreate, CommentUpdate, CommentResponse, PaginatedComments
from app.utils.mention_parser import resolve_mention_user_ids


async def create_comment(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    data: CommentCreate,
    user_id: uuid.UUID,
) -> CommentResponse:
    await _require_project_member(db, project_id, user_id)
    task = await _get_task_or_404(db, project_id, task_id)

    # parent_id geçerliliği
    parent = None
    if data.parent_id:
        parent = await _get_comment_or_404(db, task_id, data.parent_id)

    comment = TaskComment(
        task_id=task_id,
        user_id=user_id,
        parent_id=data.parent_id,
        content=data.content,
    )
    db.add(comment)
    await db.flush()  # commit öncesi ID al

    # Mention → bildirim
    mentioned_users = await resolve_mention_user_ids(data.content, db)
    mentioned_ids = {u.id for u in mentioned_users}

    for uid in mentioned_ids:
        if uid != user_id:
            await _create_notification(
                db,
                org_id=org_id,
                user_id=uid,
                actor_id=user_id,
                notification_type="mention",
                task=task,
                comment_id=comment.id,
            )

    # Görev assignee + reporter → bildirim (mention değillerse)
    notify_ids: set[uuid.UUID] = set()
    if task.assignee_id and task.assignee_id != user_id:
        notify_ids.add(task.assignee_id)
    if task.reporter_id and task.reporter_id != user_id:
        notify_ids.add(task.reporter_id)

    # Reply ise parent yorum sahibine bildirim
    if parent and parent.user_id != user_id:
        notify_ids.add(parent.user_id)

    for uid in notify_ids - mentioned_ids:
        await _create_notification(
            db,
            org_id=org_id,
            user_id=uid,
            actor_id=user_id,
            notification_type="comment_added",
            task=task,
            comment_id=comment.id,
        )

    await _log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=user_id,
        action="comment_added",
        entity_id=comment.id,
    )

    await db.commit()
    await db.refresh(comment)
    return CommentResponse.from_model(comment)


async def list_comments(
    db: AsyncSession,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    page: int,
    limit: int,
) -> PaginatedComments:
    await _require_project_member(db, project_id, user_id)
    await _get_task_or_404(db, project_id, task_id)

    offset = (page - 1) * limit

    total_result = await db.execute(
        select(func.count()).where(TaskComment.task_id == task_id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    comments = result.scalars().all()
    items = [CommentResponse.from_model(c) for c in comments]

    return PaginatedComments(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_next=(offset + len(items)) < total,
    )


async def update_comment(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: uuid.UUID,
    data: CommentUpdate,
    user_id: uuid.UUID,
) -> CommentResponse:
    await _require_project_member(db, project_id, user_id)
    comment = await _get_comment_active_or_404(db, comment_id)

    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Yalnızca kendi yorumunuzu düzenleyebilirsiniz")

    comment.content = data.content
    comment.updated_at = datetime.now(timezone.utc)
    comment.is_edited = True

    await _log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=comment.task_id,
        actor_id=user_id,
        action="comment_updated",
        entity_id=comment_id,
    )

    await db.commit()
    await db.refresh(comment)
    return CommentResponse.from_model(comment)


async def delete_comment(
    db: AsyncSession,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await _require_project_member(db, project_id, user_id)
    comment = await _get_comment_active_or_404(db, comment_id)

    is_owner = comment.user_id == user_id
    is_manager = await _is_project_manager(db, project_id, user_id)

    if not is_owner and not is_manager:
        raise HTTPException(status_code=403, detail="Bu yorumu silme yetkiniz yok")

    comment.deleted_at = datetime.now(timezone.utc)
    comment.content = None  # nullable=True — spec: {"content": null, "is_deleted": true}

    await _log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=comment.task_id,
        actor_id=user_id,
        action="comment_deleted",
        entity_id=comment_id,
    )

    await db.commit()


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

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


async def _get_comment_or_404(db: AsyncSession, task_id: uuid.UUID, comment_id: uuid.UUID) -> TaskComment:
    """parent_id validasyonu için — silinmemiş + aynı task'a ait olmalı."""
    result = await db.execute(
        select(TaskComment).where(
            TaskComment.id == comment_id,
            TaskComment.task_id == task_id,
            TaskComment.deleted_at.is_(None),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=400, detail="Geçersiz parent yorum ID'si")
    return comment


async def _get_comment_active_or_404(db: AsyncSession, comment_id: uuid.UUID) -> TaskComment:
    """update/delete için — sadece silinmemiş yorum."""
    result = await db.execute(
        select(TaskComment).where(
            TaskComment.id == comment_id,
            TaskComment.deleted_at.is_(None),
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı")
    return comment


async def _require_project_member(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Bu projeye erişim yetkiniz yok")


async def _is_project_manager(db: AsyncSession, project_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role.in_(["manager", "owner"]),
        )
    )
    return result.scalar_one_or_none() is not None


async def _create_notification(
    db: AsyncSession,
    *,
    org_id: uuid.UUID | None,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    notification_type: str,
    task: Task,
    comment_id: uuid.UUID,
) -> None:
    type_to_title = {
        "mention": f"'{task.title}' görevinde senden bahsedildi",
        "comment_added": f"'{task.title}' görevine yeni yorum eklendi",
    }
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=type_to_title.get(notification_type, "Yeni bildirim"),
        body=None,
        link=f"/tasks/{task.id}#comment-{comment_id}",
    )
    db.add(notification)


async def _log_activity(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    entity_id: uuid.UUID,
) -> None:
    log = ActivityLog(
        organization_id=org_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=actor_id,
        action=action,
        entity_type="comment",
        entity_id=entity_id,
    )
    db.add(log)