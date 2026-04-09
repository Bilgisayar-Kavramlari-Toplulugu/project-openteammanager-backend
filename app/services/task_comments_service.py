import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task_comment import TaskComment
from app.schemas.task_comments import CommentCreate, CommentUpdate, CommentResponse, PaginatedComments
from app.utils.mention_parser import resolve_mention_user_ids
from app.services.helpers import require_project_member, is_project_manager, get_task_or_404, log_activity
from app.services.notification_service import create_notification

async def create_comment(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID, data: CommentCreate, user_id: uuid.UUID) -> CommentResponse:
    await require_project_member(db, project_id, user_id)
    task = await get_task_or_404(db, project_id, task_id)

    # parent_id geçerliliğini kontrol et
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
            await create_notification(
                db,
                user_id=uid,
                notification_type="mention",
                title=f"'{task.title}' görevinde senden bahsedildi",
                link=f"/tasks/{task.id}#comment-{comment.id}",
            )

    # Görev assignee + reporter → bildirim oluştur (mention değillerse)
    notify_ids: set[uuid.UUID] = set()
    if task.assignee_id and task.assignee_id != user_id:
        notify_ids.add(task.assignee_id)
    if task.reporter_id and task.reporter_id != user_id:
        notify_ids.add(task.reporter_id)

    # Reply ise parent yorum sahibine bildirim oluştur
    if parent and parent.user_id != user_id:
        notify_ids.add(parent.user_id)

    for uid in notify_ids - mentioned_ids:
        await create_notification(
            db,
            user_id=uid,
            notification_type="mention",
            title=f"'{task.title}' görevinde senden bahsedildi",
            link=f"/tasks/{task.id}#comment-{comment.id}"
        )

    await log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=task_id,
        actor_id=user_id,
        action="comment_added",
        entity_type="comment",
        entity_id=comment.id
    )

    await db.commit()
    await db.refresh(comment)
    return CommentResponse.from_model(comment)


async def list_comments(db: AsyncSession, project_id: uuid.UUID, task_id: uuid.UUID, user_id: uuid.UUID, page: int, limit: int) -> PaginatedComments:
    await require_project_member(db, project_id, user_id)
    await get_task_or_404(db, project_id, task_id)

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


async def update_comment(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, comment_id: uuid.UUID, data: CommentUpdate, user_id: uuid.UUID) -> CommentResponse:
    await require_project_member(db, project_id, user_id)
    comment = await _get_comment_active_or_404(db, comment_id)

    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Yalnızca kendi yorumunuzu düzenleyebilirsiniz")

    comment.content = data.content
    comment.updated_at = datetime.now(timezone.utc)
    comment.is_edited = True

    await log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=comment.task_id,
        actor_id=user_id,
        action="comment_updated",
        entity_type="comment",
        entity_id=comment.id
    )

    await db.commit()
    await db.refresh(comment)
    return CommentResponse.from_model(comment)


async def delete_comment(db: AsyncSession, org_id: uuid.UUID, project_id: uuid.UUID, comment_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await require_project_member(db, project_id, user_id)
    comment = await _get_comment_active_or_404(db, comment_id)

    is_owner = comment.user_id == user_id
    is_manager = await is_project_manager(db, project_id, user_id)

    if not is_owner and not is_manager:
        raise HTTPException(status_code=403, detail="Bu yorumu silme yetkiniz yok")

    comment.deleted_at = datetime.now(timezone.utc)
    comment.content = None  # nullable=True — spec: {"content": null, "is_deleted": true}

    await log_activity(
        db,
        org_id=org_id,
        project_id=project_id,
        task_id=comment.task_id,
        actor_id=user_id,
        action="comment_deleted",
        entity_type="comment",
        entity_id=comment.id    # comment_id
    )

    await db.commit()


# ---- Yardımcı fonksiyonlar ---------------------

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