"""Bản ghi sự kiện 164 byte (LogRecord) cho các service: hash dạng hex, UUID, số nguyên như cột DB.

Bố cục byte và ràng buộc nằm ở app.core.record (tài liệu kỹ thuật 5.4.1, có test-vectors); file này chỉ đổi
kiểu dữ liệu qua lại, không tự mã hóa byte.
"""
import hashlib
import uuid

from app.core import record as rec

RECORD_SIZE = rec.RECORD_LENGTH
GENESIS_HASH = "0" * 64

EVENT_A, EVENT_E, EVENT_C, EVENT_D = (int(t) for t in rec.EventType)
EVENT_LETTERS = {int(t): t.name for t in rec.EventType}
RESULT_NONE = int(rec.Result.NOT_APPLICABLE)
RESULT_CODES = {k: int(v) for k, v in rec.RESULT_FROM_DB.items()}  # UNCHANGED / CHANGED / NO_BASELINE


def encode(*, seq: int, event_type: int, file_hash: str, case_id, actor_id, ts: int, result: int,
           ref_seq: int | None, prev_record_hash: str) -> bytes:
    return rec.Record(
        seq=seq, type=rec.EventType(event_type), file_hash=bytes.fromhex(file_hash),
        case_ref=rec.ref32(_uuid(case_id)), actor_ref=rec.ref32(_uuid(actor_id)), ts=ts,
        result=rec.Result(result), ref_seq=ref_seq or 0, prev_record_hash=bytes.fromhex(prev_record_hash),
    ).encode()


def decode(raw: bytes) -> dict:
    """Ném RecordError (ValueError) khi sai độ dài, nhãn, loại, kết quả hay ràng buộc."""
    r = rec.decode(raw)
    return {
        "seq": r.seq, "eventType": int(r.type), "fileHash": r.file_hash.hex(),
        "caseId": _ref_uuid(r.case_ref), "actorId": _ref_uuid(r.actor_ref),
        "ts": r.ts, "result": int(r.result), "refSeq": r.ref_seq or None, "prevRecordHash": r.prev_record_hash.hex(),
    }


def record_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _uuid(value) -> uuid.UUID | None:
    return None if value is None else value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _ref_uuid(ref: bytes) -> str | None:
    return None if ref == rec.ZERO32 else str(uuid.UUID(bytes=ref[:16]))
