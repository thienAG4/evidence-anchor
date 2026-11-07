"""Ghi thêm LogRecord (164 byte, nối chuỗi). Gọi trong cùng thao tác database với dòng FileHash / AppraisalStep /
Dossier / IntegrityCheck tương ứng, trước khi commit."""
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core import log_record as lr
from app.db.enums import CaseRole
from app.db.models import CaseParticipant, CourtCase, LogRecord

# Khóa theo transaction: 2 request cùng lúc không cùng lấy một bản ghi liền trước (chuỗi rẽ nhánh)
CHAIN_LOCK_KEY = 0x45564348  # "EVCH"
# Worker neo LISTEN kênh này: có bản ghi mới (hoặc bấm Neo ngay) thì chạy vòng neo ngay, không đợi hết chu kỳ
WAKE_CHANNEL = "anchor_wake"


def wake_anchor_worker(db: Session) -> None:
    """Postgres chỉ gửi NOTIFY khi transaction commit: rollback thì worker không bị đánh thức."""
    db.execute(text(f"NOTIFY {WAKE_CHANNEL}"))


def unix_seconds(value: str | datetime) -> int:
    """Chuỗi giờ đã băm (hashed_at) hoặc datetime -> số giây Unix."""
    return int((datetime.fromisoformat(value) if isinstance(value, str) else value).timestamp())


def result_code(result) -> int:
    return lr.RESULT_CODES[result.value] if result is not None else lr.RESULT_NONE


def append_record(db: Session, *, event_type: int, file_hash: str, actor_id, ts: int,
                  result: int = lr.RESULT_NONE, case_id=None, ref_seq: int | None = None) -> LogRecord:
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CHAIN_LOCK_KEY})
    prev = db.scalar(select(LogRecord.record_hash).order_by(LogRecord.seq.desc()).limit(1)) or lr.GENESIS_HASH
    # seq cuối + 1 dưới khóa: thao tác rollback thì seq được cấp lại, worker neo luôn thấy dãy seq liền nhau
    seq = db.scalar(select(func.coalesce(func.max(LogRecord.seq), 0) + 1))
    raw = lr.encode(seq=seq, event_type=event_type, file_hash=file_hash, case_id=case_id, actor_id=actor_id,
                    ts=ts, result=result, ref_seq=ref_seq, prev_record_hash=prev)
    record = LogRecord(seq=seq, event_type=event_type, file_hash=file_hash, case_id=case_id, actor_id=actor_id,
                       ts=ts, result=result, ref_seq=ref_seq, prev_record_hash=prev,
                       record_hash=lr.record_hash(raw), raw=raw)
    db.add(record)
    db.flush()
    wake_anchor_worker(db)
    return record


def case_of_clerk_and_party(db: Session, clerk_id, party_id):
    """Vụ (sớm nhất theo số vụ) mà clerk là thư ký và party tham gia: case_id cho bản ghi E thư ký đối chiếu."""
    clerk_cases = select(CaseParticipant.case_id).where(CaseParticipant.user_id == clerk_id,
                                                        CaseParticipant.role_in_case == CaseRole.CLERK)
    return db.scalar(select(CourtCase.id).join(CaseParticipant, CaseParticipant.case_id == CourtCase.id)
                     .where(CaseParticipant.user_id == party_id, CourtCase.id.in_(clerk_cases))
                     .order_by(CourtCase.case_number).limit(1))
