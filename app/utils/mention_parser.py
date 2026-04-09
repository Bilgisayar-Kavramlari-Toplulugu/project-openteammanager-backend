import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

MENTION_PATTERN = re.compile(r"@([\w]+)", re.UNICODE)


def extract_mentions(content: str) -> set[str]:
    """@username mention'larını parse eder. Örn: 'Merhaba @ahmet!' → {'ahmet'}"""
    if not content:
        return set()
    return set(MENTION_PATTERN.findall(content))


async def resolve_mention_user_ids(content: str, db: AsyncSession) -> list:
    """Mention edilen username'leri User nesnelerine çevirir. Bulunamayanlar atlanır."""
    from app.models.user import User  # circular import önlemi

    usernames = extract_mentions(content)
    if not usernames:
        return []

    result = await db.execute(
        select(User).where(User.username.in_(usernames))
    )
    return result.scalars().all()