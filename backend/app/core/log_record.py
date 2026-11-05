"""Bản ghi sự kiện 164 byte (LogRecord): mỗi sự kiện A/E/C/D một bản ghi, nối chuỗi bằng prev_record_hash.

Bố cục raw (big-endian, đúng thứ tự cột trong docs/entities.md):

    seq               8   uint64
    event_type        2   uint16   1 = A, 2 = E, 3 = C, 4 = D
    file_hash        32   SHA-256 nhị phân
    case_id          36   UUID dạng chữ (36 ký tự ASCII); trống = 00000000-0000-0000-0000-000000000000
    actor_id         36   UUID dạng chữ
    ts                8   uint64   số giây Unix
    result            2   uint16   0 = A/D, 1 = UNCHANGED, 2 = CHANGED, 3 = NO_BASELINE
    ref_seq           8   uint64   0 = không có
    prev_record_hash 32   SHA-256 nhị phân; bản ghi đầu tiên = 32 byte 0
                    ---
                    164

record_hash = SHA256(raw) — cũng là lá Merkle khi neo.
"""
import hashlib
import struct
import uuid

RECORD_SIZE = 164
NIL_UUID = str(uuid.UUID(int=0))
GENESIS_HASH = "0" * 64

EVENT_A, EVENT_E, EVENT_C, EVENT_D = 1, 2, 3, 4
EVENT_LETTERS = {EVENT_A: "A", EVENT_E: "E", EVENT_C: "C", EVENT_D: "D"}
RESULT_NONE, RESULT_UNCHANGED, RESULT_CHANGED, RESULT_NO_BASELINE = 0, 1, 2, 3
RESULT_CODES = {"UNCHANGED": RESULT_UNCHANGED, "CHANGED": RESULT_CHANGED, "NO_BASELINE": RESULT_NO_BASELINE}


def encode(*, seq: int, event_type: int, file_hash: str, case_id, actor_id, ts: int, result: int,
           ref_seq: int | None, prev_record_hash: str) -> bytes:
    raw = (struct.pack(">QH", seq, event_type) + bytes.fromhex(file_hash)
           + str(case_id or NIL_UUID).encode("ascii") + str(actor_id).encode("ascii")
           + struct.pack(">QHQ", ts, result, ref_seq or 0) + bytes.fromhex(prev_record_hash))
    if len(raw) != RECORD_SIZE:
        raise ValueError(f"Bản ghi phải đúng {RECORD_SIZE} byte, đang là {len(raw)}.")
    return raw


def decode(raw: bytes) -> dict:
    if len(raw) != RECORD_SIZE:
        raise ValueError(f"Bản ghi phải đúng {RECORD_SIZE} byte, đang là {len(raw)}.")
    seq, event_type = struct.unpack_from(">QH", raw, 0)
    ts, result, ref_seq = struct.unpack_from(">QHQ", raw, 114)
    case_id = raw[42:78].decode("ascii")
    return {
        "seq": seq, "eventType": event_type, "fileHash": raw[10:42].hex(),
        "caseId": None if case_id == NIL_UUID else case_id, "actorId": raw[78:114].decode("ascii"),
        "ts": ts, "result": result, "refSeq": ref_seq or None, "prevRecordHash": raw[132:164].hex(),
    }


def record_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
