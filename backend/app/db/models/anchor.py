import uuid
from datetime import datetime

from sqlalchemy import (CHAR, BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, LargeBinary,
                        SmallInteger, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, created_at_column
from app.db.enums import ChainTxKind, ChainTxStatus


class AnchorBatch(UUIDPk, Base):
    """Một đợt neo: các bản ghi from_seq..to_seq liền nhau. Ghi một lần lúc chốt đợt, trước khi gửi giao dịch."""
    __tablename__ = "anchor_batch"
    __table_args__ = (CheckConstraint("from_seq <= to_seq", name="seq_range"),)

    batch_no: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    from_seq: Mapped[int] = mapped_column(BigInteger, ForeignKey("log_record.seq"), nullable=False)
    to_seq: Mapped[int] = mapped_column(BigInteger, ForeignKey("log_record.seq"), nullable=False)
    prev_root: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # đợt 1: toàn số 0
    root: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # đúng các byte gửi lên chuỗi
    nonce: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class AnchorLeaf(UUIDPk, Base):
    """Mỗi LogRecord là một lá, thuộc đúng một đợt. Cây hai tầng: nhóm theo người ghi -> subRoot -> root đợt."""
    __tablename__ = "anchor_leaf"
    __table_args__ = (UniqueConstraint("batch_id", "group_index", "leaf_index"),)

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("anchor_batch.id"), nullable=False)
    record_seq: Mapped[int] = mapped_column(BigInteger, ForeignKey("log_record.seq"), unique=True, nullable=False)
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    leaf_index: Mapped[int] = mapped_column(Integer, nullable=False)
    leaf_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)  # SHA256(0x00 ‖ recordHash)
    group_path: Mapped[list] = mapped_column(JSONB, nullable=False)  # lá -> subRoot: [{"side": "L"|"R", "hash"}]
    batch_path: Mapped[list] = mapped_column(JSONB, nullable=False)  # subRoot -> root đợt


class ChainTx(UUIDPk, Base):
    """Mọi giao dịch ví neo đã ký. Ghi trước khi phát lên mạng, để tiến trình chết giữa chừng vẫn biết tx_hash."""
    __tablename__ = "chain_tx"

    kind: Mapped[ChainTxKind] = mapped_column(Enum(ChainTxKind, name="chain_tx_kind"), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anchor_batch.id"), index=True)  # ANCH, NOOP
    nonce: Mapped[int] = mapped_column(BigInteger, nullable=False)  # giao dịch thay thế dùng lại nonce cũ
    tx_hash: Mapped[str] = mapped_column(CHAR(66), unique=True, nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    replaces_tx_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chain_tx.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChainTxResult(UUIDPk, Base):
    __tablename__ = "chain_tx_result"
    __table_args__ = (UniqueConstraint("tx_id", "status"),)

    tx_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chain_tx.id"), nullable=False)
    status: Mapped[ChainTxStatus] = mapped_column(Enum(ChainTxStatus, name="chain_tx_status"), nullable=False)
    block_number: Mapped[int | None] = mapped_column(BigInteger)
    block_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # mốc thời gian chính thức của đợt
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AnchorState(Base):
    """Một dòng duy nhất (id = 1), được sửa: nonce kế tiếp và cờ dừng job neo."""
    __tablename__ = "anchor_state"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    next_nonce: Mapped[int] = mapped_column(BigInteger, nullable=False)
    halted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    halted_reason: Mapped[str | None] = mapped_column(Text)
    # Nút "Neo ngay": worker thấy giá trị này thì chốt các bản ghi đang chờ không đợi mốc ngày, rồi xóa
    anchor_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
