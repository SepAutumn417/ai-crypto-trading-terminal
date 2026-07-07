from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ConfigVersionModel(Base):
    __tablename__ = "config_versions"
    __table_args__ = (
        UniqueConstraint("config_type", "version_label", name="uq_config_versions_type_label"),
        # 部分唯一索引：每种 config_type 同时只能有一个 is_active=true
        # 与 alembic migration 创建的 idx_config_versions_active 保持一致
        Index(
            "idx_config_versions_active",
            "config_type",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    config_type: Mapped[str] = mapped_column(String(32), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)