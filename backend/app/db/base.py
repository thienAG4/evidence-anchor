import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDPk:
    """Khóa chính UUID sinh phía ứng dụng."""
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# Bảng chỉ ghi thêm (F6): migration REVOKE UPDATE, DELETE trên các bảng này cho tài khoản ứng dụng.
APPEND_ONLY_TABLES = (
    "submission", "file_hash", "anchor", "anchor_leaf", "integrity_check",
    "appraisal_step", "dossier", "dossier_item", "access_log",
)
