"""Các byte ghi vào Input Data của giao dịch neo (big-endian). Mỗi loại mở đầu bằng 4 byte ASCII tên loại.

ANCH (92 byte): "ANCH" | batch_no u64 | from_seq u64 | to_seq u64 | prev_root 32 | root 32
KEYR (46 byte): "KEYR" | key_id u16 | khóa công khai Ed25519 32 | from_seq u64 (bản ghi đầu tiên ký bằng khóa này)
NOOP (12 byte): "NOOP" | batch_no u64 (đợt có giao dịch kẹt bị hủy)
"""
import struct

ANCH_SIZE = 92


def encode_anch(batch_no: int, from_seq: int, to_seq: int, prev_root: str, root: str) -> bytes:
    return b"ANCH" + struct.pack(">QQQ", batch_no, from_seq, to_seq) + bytes.fromhex(prev_root) + bytes.fromhex(root)


def decode_anch(payload: bytes) -> dict:
    if len(payload) != ANCH_SIZE or payload[:4] != b"ANCH":
        raise ValueError("Không phải payload ANCH.")
    batch_no, from_seq, to_seq = struct.unpack(">QQQ", payload[4:28])
    return {"batchNo": batch_no, "fromSeq": from_seq, "toSeq": to_seq,
            "prevRoot": payload[28:60].hex(), "root": payload[60:92].hex()}


def encode_keyr(key_id: int, public_key: bytes, from_seq: int) -> bytes:
    if len(public_key) != 32:
        raise ValueError("Khóa công khai Ed25519 phải 32 byte.")
    return b"KEYR" + struct.pack(">H", key_id) + public_key + struct.pack(">Q", from_seq)


def encode_noop(batch_no: int) -> bytes:
    return b"NOOP" + struct.pack(">Q", batch_no)
