"""Dòng KEYR, NOOP ghi lên chuỗi, cùng quy ước với ANCH trong app.core.payload: nhãn 4 byte ASCII ‖ phiên bản 1 byte ‖
payload, big-endian.

KEYR (37 byte): "KEYR" | version | keyId u32 | địa chỉ khóa ký biên nhận (EIP-191) 20 | fromSeq u64
    keyId cùng kiểu với keyId trong 58 byte được ký (app.core.signing.build_signed_message);
    fromSeq: bản ghi đầu tiên dùng khóa này.
NOOP (13 byte): "NOOP" | version | nonce u64 (nonce của giao dịch kẹt bị thay bằng NOOP)
"""
import struct
from dataclasses import dataclass

from app.core.payload import VERSION, PayloadError

KEYR_TAG, NOOP_TAG = b"KEYR", b"NOOP"
_KEYR = struct.Struct(">4sBI20sQ")
_NOOP = struct.Struct(">4sBQ")
KEYR_LENGTH, NOOP_LENGTH = _KEYR.size, _NOOP.size
assert (KEYR_LENGTH, NOOP_LENGTH) == (37, 13)


@dataclass(frozen=True)
class Keyr:
    key_id: int
    address: str  # 0x + 40 hex chữ thường
    from_seq: int


def encode_keyr(key_id: int, signer_address: str, from_seq: int) -> bytes:
    try:
        address = bytes.fromhex(signer_address.removeprefix("0x"))
    except ValueError:
        raise PayloadError("Địa chỉ khóa ký không phải hex.") from None
    if len(address) != 20:
        raise PayloadError("Địa chỉ khóa ký phải 20 byte.")
    if not 0 <= key_id < 2**32 or from_seq < 1:
        raise PayloadError("keyId phải vừa u32, fromSeq phải từ 1.")
    return _KEYR.pack(KEYR_TAG, VERSION, key_id, address, from_seq)


def decode_keyr(data: bytes) -> Keyr:
    if len(data) != KEYR_LENGTH:
        raise PayloadError(f"KEYR phải dài {KEYR_LENGTH} byte, nhận {len(data)}")
    tag, version, key_id, address, from_seq = _KEYR.unpack(data)
    if tag != KEYR_TAG:
        raise PayloadError(f"nhãn {tag!r} không phải {KEYR_TAG!r}")
    if version != VERSION:
        raise PayloadError(f"phiên bản {version} không hỗ trợ")
    if from_seq < 1:
        raise PayloadError("fromSeq phải từ 1")
    return Keyr(key_id, "0x" + address.hex(), from_seq)


def encode_noop(nonce: int) -> bytes:
    if not 0 <= nonce < 2**64:
        raise PayloadError("nonce phải vừa u64.")
    return _NOOP.pack(NOOP_TAG, VERSION, nonce)


def decode_noop(data: bytes) -> int:
    """Trả về nonce ghi trong NOOP."""
    if len(data) != NOOP_LENGTH:
        raise PayloadError(f"NOOP phải dài {NOOP_LENGTH} byte, nhận {len(data)}")
    tag, version, nonce = _NOOP.unpack(data)
    if tag != NOOP_TAG:
        raise PayloadError(f"nhãn {tag!r} không phải {NOOP_TAG!r}")
    if version != VERSION:
        raise PayloadError(f"phiên bản {version} không hỗ trợ")
    return nonce
