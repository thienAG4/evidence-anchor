import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.db.enums import AppealType


class Dossier(UUIDPk, Base):
    """Bản ghi chốt (D) khi hồ sơ rời Tòa sơ thẩm."""
    __tablename__ = "dossier"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("court_case.id"), nullable=False, index=True)
    appeal_type: Mapped[AppealType] = mapped_column(Enum(AppealType, name="appeal_type"), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DossierItem(UUIDPk, Base):
    __tablename__ = "dossier_item"
    __table_args__ = (UniqueConstraint("dossier_id", "position"),)

    dossier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dossier.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
