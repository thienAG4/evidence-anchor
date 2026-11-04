import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.db.enums import AppealType, CaseRole, CaseStatus


class CourtCase(UUIDPk, Base):
    __tablename__ = "court_case"

    case_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    court_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status"), nullable=False, default=CaseStatus.OPEN)
    appeal_type: Mapped[AppealType | None] = mapped_column(Enum(AppealType, name="appeal_type"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)


class CaseParticipant(UUIDPk, Base):
    __tablename__ = "case_participant"
    __table_args__ = (UniqueConstraint("case_id", "user_id", "role_in_case"),)

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("court_case.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    role_in_case: Mapped[CaseRole] = mapped_column(Enum(CaseRole, name="case_role"), nullable=False)
