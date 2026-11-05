import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk
from app.db.enums import CheckTarget, FileResult, MatchResult, SubmissionType


class Submission(UUIDPk, Base):
    """Một lần nộp = một biên nhận = một Bundle. Chỉ ghi thêm; trạng thái neo suy ra từ bản ghi của từng file."""
    __tablename__ = "submission"
    __table_args__ = (
        UniqueConstraint("case_id", "lot_no"),
        # Lô tại Tòa phải có vụ, số lô, nơi nộp (nằm trong hash tổng); lưu chứng SELF thì không có vụ.
        CheckConstraint(
            "(type = 'COURT_LOT') = (case_id IS NOT NULL AND lot_no IS NOT NULL AND place IS NOT NULL)",
            name="court_lot_fields",
        ),
    )

    receipt_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    type: Mapped[SubmissionType] = mapped_column(Enum(SubmissionType, name="submission_type"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("court_case.id"))
    lot_no: Mapped[int | None] = mapped_column(Integer)
    place: Mapped[str | None] = mapped_column(String(200))
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bundle_scheme: Mapped[str] = mapped_column(String(30), nullable=False)
    habc: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    bundled_at: Mapped[str] = mapped_column(String(40), nullable=False)  # đúng chuỗi đã băm
    bundle_time_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    lot_meta_hash: Mapped[str | None] = mapped_column(CHAR(64))  # chỉ COURT_LOT
    bundle_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)  # Ed25519 base64 trên receipt_json
    receipt_json: Mapped[dict] = mapped_column(JSONB, nullable=False)


class FileHash(UUIDPk, Base):
    __tablename__ = "file_hash"
    __table_args__ = (UniqueConstraint("submission_id", "position"),)

    submission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("submission.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, index=True)  # Hi
    hashed_at: Mapped[str] = mapped_column(String(40), nullable=False)  # đúng chuỗi đã băm
    time_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # Hti
    leaf_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # Ha
    sleep_after_seconds: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    baseline_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_hash.id"))
    result: Mapped[FileResult | None] = mapped_column(Enum(FileResult, name="file_result"))  # chỉ file trong lô
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_seq: Mapped[int] = mapped_column(  # bản ghi A (lưu chứng) hoặc E (file trong lô)
        BigInteger, ForeignKey("log_record.seq"), unique=True, nullable=False)


class IntegrityCheck(UUIDPk, Base):
    """Mỗi lần tính lại (lô, file, hồ sơ chốt) ghi thêm 1 dòng, không sửa bản ghi gốc."""
    __tablename__ = "integrity_check"
    __table_args__ = (
        CheckConstraint(
            "(target = 'LOT' AND submission_id IS NOT NULL AND file_id IS NULL AND dossier_id IS NULL)"
            " OR (target = 'FILE' AND file_id IS NOT NULL AND submission_id IS NULL AND dossier_id IS NULL)"
            " OR (target = 'DOSSIER' AND dossier_id IS NOT NULL AND submission_id IS NULL AND file_id IS NULL)",
            name="one_target",
        ),
    )

    target: Mapped[CheckTarget] = mapped_column(Enum(CheckTarget, name="check_target"), nullable=False)
    submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("submission.id"), index=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_hash.id"), index=True)
    dossier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("dossier.id"), index=True)
    result: Mapped[MatchResult] = mapped_column(Enum(MatchResult, name="match_result"), nullable=False)
    phase: Mapped[str | None] = mapped_column(String(100))  # giai đoạn tố tụng khi đối chiếu (giao diện thư ký)
    checked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_seq: Mapped[int] = mapped_column(  # bản ghi E (đối chiếu)
        BigInteger, ForeignKey("log_record.seq"), unique=True, nullable=False)
