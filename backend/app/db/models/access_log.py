import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column
from app.db.enums import AccessResult


class AccessLog(Base):
    """Chỉ ghi thêm; ghi cả thao tác bị từ chối (DENY)."""
    __tablename__ = "access_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(100))
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("court_case.id"), index=True)
    result: Mapped[AccessResult] = mapped_column(Enum(AccessResult, name="access_result"), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = created_at_column()
