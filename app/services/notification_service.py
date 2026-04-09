import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.notification import Notification

async def create_notification(db: AsyncSession, *, user_id: uuid.UUID, notification_type: str, title: str, body: str | None = None, link: str | None = None) -> None:
    """Bildirim oluşturur.
      title ve link çağıran service tarafından hazırlanır.
    """
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        body=body,
        link=link
    )
    db.add(notification)