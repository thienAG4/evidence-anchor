import uuid
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.db.enums import AppraisalStepType, MatchResult


class AppraisalStep(UUIDPk, Base):
    __tablename__ = "appraisal_step"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("file_hash.id"), nullable=False, index=True)
    step: Mapped[AppraisalStepType] = mapped_column(Enum(AppraisalStepType, name="appraisal_step_type"), nullable=False)
    file_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    result: Mapped[MatchResult] = mapped_column(Enum(MatchResult, name="match_result"), nullable=False)  # so với E
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_seq: Mapped[int] = mapped_column(  # bản ghi C
        BigInteger, ForeignKey("log_record.seq"), unique=True, nullable=False)
