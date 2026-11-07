import uuid
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk


class OtsStamp(UUIDPk, Base):
    """OpenTimestamps cho bản ghi A (tài liệu kỹ thuật 6.9; Final_ERD: gộp OtsUpgrade vào một bảng được sửa).

    Trình duyệt đương sự đóng dấu fileHash rồi gửi bản chờ lên; job nâng cấp điền ots_complete khi Bitcoin xác nhận.
    Được UPDATE (ots_complete, bitcoin_block, upgraded_at): ngoại lệ thứ hai sau anchor_state.
    """
    __tablename__ = "ots_stamp"

    record_seq: Mapped[int] = mapped_column(BigInteger, ForeignKey("log_record.seq"), unique=True, nullable=False)
    file_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    ots_pending: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # bản chờ, giữ nguyên như đã nhận
    ots_complete: Mapped[bytes | None] = mapped_column(LargeBinary)  # bản đã nâng cấp (có block Bitcoin)
    bitcoin_block: Mapped[int | None] = mapped_column(BigInteger)  # block Bitcoin thấp nhất xác nhận
    stamped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # để báo động sau 48 giờ
    upgraded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
