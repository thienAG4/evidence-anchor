"""Bản ghi nhật ký 164 byte và chuỗi nối (tài liệu kỹ thuật 5.4.1; bố cục byte theo tab 1026_Tech,
người ghi / vụ án theo 1027_Tech: UserID và mã vụ án nội bộ, không salt).

Bố cục (big-endian, trường rỗng điền số 0 đúng độ dài, không bỏ trường):
    label "EVC-REC-v1" 10 | seq u64 8 | type u8 1 | fileHash 32 | caseRef 32 | actorRef 32
    | ts u64 8 | result u8 1 | refSeq u64 8 | prevRecordHash 32                         = 164 byte
caseRef / actorRef = UUID 16 byte + 16 byte số 0 (loại A: caseRef toàn số 0).
ts = số giây Unix (không phụ thuộc múi giờ; giao diện hiển thị giờ Việt Nam).
recordHash = SHA256(164 byte); bản ghi seq = 1 có prevRecordHash toàn số 0.
"""
import hashlib
import struct
import uuid
from dataclasses import dataclass
from enum import IntEnum

LABEL = b"EVC-REC-v1"
RECORD_LENGTH = 164
ZERO32 = bytes(32)
_LAYOUT = struct.Struct(">10sQB32s32s32sQBQ32s")
assert _LAYOUT.size == RECORD_LENGTH


class EventType(IntEnum):
    A = 1  # lưu chứng
    E = 2  # đối chiếu
    C = 3  # giám định
    D = 4  # chốt hồ sơ


class Result(IntEnum):
    NOT_APPLICABLE = 0
    MATCH = 1
    MISMATCH = 2
    NO_A = 3  # không có bản lưu chứng A để so


# Giá trị kết quả trong DB (FileResult / MatchResult) -> mã byte trong bản ghi
RESULT_FROM_DB = {"UNCHANGED": Result.MATCH, "CHANGED": Result.MISMATCH, "NO_BASELINE": Result.NO_A}


class RecordError(ValueError):
    """Bản ghi sai định dạng: bên kiểm tra phải từ chối."""


def ref32(value: uuid.UUID | None) -> bytes:
    """UUID -> 32 byte (16 byte UUID + 16 byte số 0); None -> toàn số 0."""
    return ZERO32 if value is None else value.bytes + bytes(16)


@dataclass(frozen=True)
class Record:
    seq: int
    type: EventType
    file_hash: bytes
    case_ref: bytes
    actor_ref: bytes
    ts: int
    result: Result
    ref_seq: int
    prev_record_hash: bytes

    def encode(self) -> bytes:
        _check(self)
        return _LAYOUT.pack(LABEL, self.seq, self.type, self.file_hash, self.case_ref, self.actor_ref,
                            self.ts, self.result, self.ref_seq, self.prev_record_hash)

    def record_hash(self) -> bytes:
        return hashlib.sha256(self.encode()).digest()


def _check(r: Record) -> None:
    for name in ("file_hash", "case_ref", "actor_ref", "prev_record_hash"):
        if len(getattr(r, name)) != 32:
            raise RecordError(f"{name} phải dài 32 byte")
    if r.seq < 1:
        raise RecordError("seq bắt đầu từ 1")
    if r.type == EventType.A and (r.case_ref != ZERO32 or r.result != Result.NOT_APPLICABLE):
        raise RecordError("bản ghi A: caseRef toàn số 0, result = không áp dụng")
    if r.seq == 1 and r.prev_record_hash != ZERO32:
        raise RecordError("bản ghi seq = 1 phải có prevRecordHash toàn số 0")
    if r.ref_seq >= r.seq:
        raise RecordError("refSeq phải trỏ về bản ghi đứng trước")


def decode(data: bytes) -> Record:
    """164 byte -> Record. Sai độ dài, sai nhãn, sai loại hay kết quả thì ném RecordError."""
    if len(data) != RECORD_LENGTH:
        raise RecordError(f"bản ghi phải dài {RECORD_LENGTH} byte, nhận {len(data)}")
    label, seq, type_, file_hash, case_ref, actor_ref, ts, result, ref_seq, prev = _LAYOUT.unpack(data)
    if label != LABEL:
        raise RecordError(f"nhãn {label!r} không phải {LABEL!r}")
    try:
        record = Record(seq, EventType(type_), file_hash, case_ref, actor_ref, ts, Result(result), ref_seq, prev)
    except ValueError as exc:
        raise RecordError(str(exc)) from None
    _check(record)
    return record


def verify_chain(raw_records: list[bytes]) -> int | None:
    """Duyệt lại chuỗi (theo seq tăng dần, liên tục từ 1). Trả về seq đầu tiên bị lệch, None nếu chuỗi đúng."""
    prev_hash, expected_seq = ZERO32, 1
    for raw in raw_records:
        try:
            record = decode(raw)
        except RecordError:
            return expected_seq
        if record.seq != expected_seq or record.prev_record_hash != prev_hash:
            return expected_seq
        prev_hash, expected_seq = hashlib.sha256(raw).digest(), expected_seq + 1
    return None
