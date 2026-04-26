import uuid
import secrets
from datetime import datetime, UTC
from sqlalchemy import String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


class Invitation(Base):
    __tablename__ = "invitations"

    __table_args__ = (
        # Aynı kullanıcıya aynı org/proje için birden fazla pending davet engelleyen unique kısıt
        UniqueConstraint(
            "organization_id", "project_id", "invited_user_id", "status",
            name="uq_invitation_pending",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    # NULL ise org daveti, dolu ise proje daveti
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    invited_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Org: owner | member   /   Proje: manager | contributor | reviewer | viewer
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending | accepted | declined
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    # invite_method org'dan kopyalanır, daveti gönderilen andaki değeri saklar
    invite_method: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(UTC)
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invited_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invited_user_id],
        lazy="raise",
    )
    inviter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[invited_by],
        lazy="raise",
    )


class InviteLink(Base):
    __tablename__ = "invite_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False,
        default=lambda: secrets.token_urlsafe(48)
    )
    # Link ile katılan kullanıcıya atanacak rol
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(UTC)
    )


class DomainAllowlist(Base):
    __tablename__ = "domain_allowlist"

    __table_args__ = (
        UniqueConstraint("organization_id", "domain", name="uq_org_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # Domain ile otomatik katılan kullanıcıya atanacak rol
    auto_role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(UTC)
    )