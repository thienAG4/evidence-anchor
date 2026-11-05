"""Dòng ghi lên chuỗi (data của giao dịch 0 ETH từ ví neo), tài liệu kỹ thuật 5.3 (1027_Tech).

Mọi dòng: nhãn 4 byte ASCII ‖ phiên bản 1 byte ‖ payload; số nguyên không dấu, big-endian.
ANCH (1027_Tech): số đợt, số bản ghi trong đợt, mã tổng hợp đợt trước, mã tổng hợp đợt này.
    "ANCH" 4 | version 1 | batchNo u64 8 | recordCount u64 8 | prevRoot 32 | root 32 = 85 byte
Độ dài từng trường 1027_Tech không ghi; lấy theo quy ước của 1026_Tech. Đợt đầu tiên có prevRoot toàn số 0.
Sai nhãn, sai phiên bản, sai độ dài thì bên kiểm tra từ chối.
"""
import struct
from dataclasses import dataclass

VERSION = 1
ANCH_TAG = b"ANCH"
ANCH_LENGTH = 85
_ANCH = struct.Struct(">4sBQQ32s32s")
assert _ANCH.size == ANCH_LENGTH


class PayloadError(ValueError):
    """Dòng sai định dạng: bên kiểm tra phải từ chối."""


@dataclass(frozen=True)
class Anch:
    batch_no: int
    record_count: int
    prev_root: bytes
    root: bytes

    def encode(self) -> bytes:
        if self.batch_no < 1 or self.record_count < 1:
            raise PayloadError("số đợt và số bản ghi phải từ 1")
        if len(self.prev_root) != 32 or len(self.root) != 32:
            raise PayloadError("prevRoot, root phải dài 32 byte")
        if self.batch_no == 1 and self.prev_root != bytes(32):
            raise PayloadError("đợt đầu tiên có prevRoot toàn số 0")
        return _ANCH.pack(ANCH_TAG, VERSION, self.batch_no, self.record_count, self.prev_root, self.root)


def decode_anch(data: bytes) -> Anch:
    if len(data) != ANCH_LENGTH:
        raise PayloadError(f"ANCH phải dài {ANCH_LENGTH} byte, nhận {len(data)}")
    tag, version, batch_no, count, prev_root, root = _ANCH.unpack(data)
    if tag != ANCH_TAG:
        raise PayloadError(f"nhãn {tag!r} không phải {ANCH_TAG!r}")
    if version != VERSION:
        raise PayloadError(f"phiên bản {version} không hỗ trợ")
    anch = Anch(batch_no, count, prev_root, root)
    anch.encode()  # kiểm các ràng buộc còn lại
    return anch
