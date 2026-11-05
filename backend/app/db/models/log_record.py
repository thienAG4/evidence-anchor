import uuid

from sqlalchemy import CHAR, BigInteger, CheckConstraint, ForeignKey, LargeBinary, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LogRecord(Base):
    """Mỗi sự kiện (A lưu chứng, E nộp lô/đối chiếu, C giám định, D chốt hồ sơ) một dòng, đúng 164 byte.

    Chỉ ghi thêm, nối chuỗi bằng prev_record_hash; mỗi bản ghi là một lá Merkle khi neo. Bố cục: app.core.log_record.
    """
    __tablename__ = "log_record"
    __table_args__ = (
        CheckConstraint("event_type BETWEEN 1 AND 4", name="event_type_range"),
        CheckConstraint("result BETWEEN 0 AND 3", name="result_range"),
        CheckConstraint("octet_length(raw) = 164", name="raw_164_bytes"),
    )

    # = seq cuối + 1, cấp trong thao tác có khóa (log_service); không dùng sequence: rollback không để lại lỗ hổng
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    event_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, index=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("court_case.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user_account.id"), nullable=False)
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)  # giây Unix, đúng con số trong raw
    result: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ref_seq: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("log_record.seq"))  # E trỏ A, C trỏ E
    prev_record_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)  # chuỗi không rẽ nhánh
    record_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
