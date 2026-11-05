"""Dòng KEYR, NOOP ghi lên chuỗi, cùng quy ước với ANCH trong app.core.payload: nhãn 4 byte ASCII ‖ phiên bản 1 byte ‖
payload, big-endian.

KEYR (35 byte): "KEYR" | version | key_no u16 | địa chỉ khóa ký biên nhận (EIP-191) 20 | from_seq u64
    (from_seq: bản ghi đầu tiên dùng khóa này)
NOOP (13 byte): "NOOP" | version | batch_no u64 (đợt có giao dịch kẹt bị hủy)
"""
import struct

from app.core.payload import VERSION


def encode_keyr(key_no: int, signer_address: str, from_seq: int) -> bytes:
    address = bytes.fromhex(signer_address.removeprefix("0x"))
    if len(address) != 20:
        raise ValueError("Địa chỉ khóa ký phải 20 byte.")
    return b"KEYR" + struct.pack(">BH", VERSION, key_no) + address + struct.pack(">Q", from_seq)


def encode_noop(batch_no: int) -> bytes:
    return b"NOOP" + struct.pack(">BQ", VERSION, batch_no)
