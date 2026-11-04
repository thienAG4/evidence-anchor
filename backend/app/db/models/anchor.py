import uuid
from datetime import date, datetime

from sqlalchemy import CHAR, BigInteger, Date, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, created_at_column
from app.db.enums import AnchorMode, AnchorResult


class Anchor(UUIDPk, Base):
    """Mỗi lần gửi giao dịch neo. Ghi sau khi biết kết quả; thử lại = Anchor mới."""
    __tablename__ = "anchor"

    mode: Mapped[AnchorMode] = mapped_column(Enum(AnchorMode, name="anchor_mode"), nullable=False)
    period_date: Mapped[date | None] = mapped_column(Date)  # DAILY
    root_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    leaf_count: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[AnchorResult] = mapped_column(Enum(AnchorResult, name="anchor_result"), nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(CHAR(66))
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    block_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class AnchorFinality(UUIDPk, Base):
    """Ghi thêm khi block chứa giao dịch neo đã chốt (finalized) — tài liệu kỹ thuật 7.1.

    Không sửa dòng Anchor: có dòng này thì lần neo đó là FINALIZED, chưa có thì mới CONFIRMED.
    """
    __tablename__ = "anchor_finality"

    anchor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anchor.id"), nullable=False, unique=True)
    tx_block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)  # block chứa giao dịch lúc chốt
    finalized_block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)  # block chốt mới nhất lúc kiểm
    created_at: Mapped[datetime] = created_at_column()


class AnchorLeaf(UUIDPk, Base):
    __tablename__ = "anchor_leaf"
    __table_args__ = (UniqueConstraint("anchor_id", "submission_id"),)

    anchor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("anchor.id"), nullable=False)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submission.id"), nullable=False, index=True)
    leaf_index: Mapped[int] = mapped_column(Integer, nullable=False)
    merkle_proof: Mapped[list] = mapped_column(JSONB, nullable=False)  # [{"side": "L"|"R", "hash": "..."}]
