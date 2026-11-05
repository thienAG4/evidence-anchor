"""Dòng ghi lên chuỗi (data của giao dịch 0 ETH từ ví neo), tài liệu kỹ thuật 5.3.

Mọi dòng: nhãn 4 byte ASCII ‖ phiên bản 1 byte ‖ payload; số nguyên không dấu, big-endian.
ANCH (theo 1026_Tech, nhóm chốt hướng A): số đợt, khoảng số thứ tự bản ghi, mã tổng hợp đợt trước, mã tổng hợp đợt này.
    "ANCH" 4 | version 1 | batchId u64 8 | fromSeq u64 8 | toSeq u64 8 | prevRoot 32 | root 32 = 93 byte
Đợt đầu tiên có prevRoot toàn số 0. Các đợt liền nhau: fromSeq đợt sau = toSeq đợt trước + 1 (xem check_contiguous),
nên bên kiểm tra phát hiện được bản ghi bị bỏ sót giữa hai đợt.
Sai nhãn, sai phiên bản, sai độ dài thì bên kiểm tra từ chối.
"""
import struct
from dataclasses import dataclass

VERSION = 1
ANCH_TAG = b"ANCH"
ANCH_LENGTH = 93
_ANCH = struct.Struct(">4sBQQQ32s32s")
assert _ANCH.size == ANCH_LENGTH


class PayloadError(ValueError):
    """Dòng sai định dạng: bên kiểm tra phải từ chối."""


@dataclass(frozen=True)
class Anch:
    batch_no: int
    from_seq: int
    to_seq: int
    prev_root: bytes
    root: bytes

    @property
    def record_count(self) -> int:
        return self.to_seq - self.from_seq + 1

    def contains(self, seq: int) -> bool:
        return self.from_seq <= seq <= self.to_seq

    def encode(self) -> bytes:
        if self.batch_no < 1 or self.from_seq < 1:
            raise PayloadError("số đợt và fromSeq phải từ 1")
        if self.to_seq < self.from_seq:
            raise PayloadError("toSeq phải ≥ fromSeq")
        if len(self.prev_root) != 32 or len(self.root) != 32:
            raise PayloadError("prevRoot, root phải dài 32 byte")
        if self.batch_no == 1 and (self.prev_root != bytes(32) or self.from_seq != 1):
            raise PayloadError("đợt đầu tiên có prevRoot toàn số 0 và fromSeq = 1")
        return _ANCH.pack(ANCH_TAG, VERSION, self.batch_no, self.from_seq, self.to_seq, self.prev_root, self.root)


def decode_anch(data: bytes) -> Anch:
    if len(data) != ANCH_LENGTH:
        raise PayloadError(f"ANCH phải dài {ANCH_LENGTH} byte, nhận {len(data)}")
    tag, version, batch_no, from_seq, to_seq, prev_root, root = _ANCH.unpack(data)
    if tag != ANCH_TAG:
        raise PayloadError(f"nhãn {tag!r} không phải {ANCH_TAG!r}")
    if version != VERSION:
        raise PayloadError(f"phiên bản {version} không hỗ trợ")
    anch = Anch(batch_no, from_seq, to_seq, prev_root, root)
    anch.encode()  # kiểm các ràng buộc còn lại
    return anch


def check_contiguous(prev: Anch, nxt: Anch) -> None:
    """Hai đợt liên tiếp phải nối nhau: số đợt +1, root nối, không hở và không chồng số thứ tự bản ghi."""
    if nxt.batch_no != prev.batch_no + 1:
        raise PayloadError(f"đợt {nxt.batch_no} không nối sau đợt {prev.batch_no}")
    if nxt.prev_root != prev.root:
        raise PayloadError(f"prevRoot của đợt {nxt.batch_no} khác root của đợt {prev.batch_no}")
    if nxt.from_seq != prev.to_seq + 1:
        raise PayloadError(f"đợt {nxt.batch_no} bắt đầu từ bản ghi {nxt.from_seq}, phải là {prev.to_seq + 1}")
