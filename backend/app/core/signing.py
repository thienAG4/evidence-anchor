"""Chữ ký biên nhận tạm theo EIP-191 (tài liệu kỹ thuật mục 6.5).

Nội dung ký dài cố định 58 byte, không ghép chuỗi tùy ý (bố cục theo tab 1026_Tech, mục 6.5):
    nhãn "EVC-RECEIPT-v1" (14) ‖ keyId u32 (4) ‖ seq u64 (8) ‖ recordHash (32), số nguyên big-endian
Khi chưa có bản ghi 164 byte, "recordHash" tạm là SHA256(biên nhận JSON) và seq là số của mã biên nhận.
Chữ ký là personal_sign (EIP-191) trên 58 byte đó: 65 byte, dạng hex "0x...".
Bên kiểm tra khôi phục địa chỉ ký từ chữ ký rồi so với địa chỉ khóa ký đã công bố,
không tin địa chỉ ghi trong biên nhận.
"""
import hashlib
import json

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.exceptions import BadSignature

RECEIPT_TAG = b"EVC-RECEIPT-v1"
SIGNED_MESSAGE_LENGTH = 58


def canonical_json(data: dict) -> bytes:
    """JSON cố định thứ tự khóa, không khoảng trắng — để ký và kiểm chữ ký cho cùng một chuỗi byte."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_signed_message(key_id: int, seq: int, record_hash: bytes) -> bytes:
    """58 byte được ký: nhãn ‖ keyId ‖ seq ‖ recordHash."""
    if len(record_hash) != 32:
        raise ValueError("recordHash phải dài 32 byte")
    message = RECEIPT_TAG + key_id.to_bytes(4, "big") + seq.to_bytes(8, "big") + record_hash
    assert len(message) == SIGNED_MESSAGE_LENGTH
    return message


def signed_message(key_no: int, seq: int, receipt: dict) -> bytes:
    """58 byte được ký cho một biên nhận JSON (recordHash tạm = SHA256 của biên nhận)."""
    return build_signed_message(key_no, seq, hashlib.sha256(canonical_json(receipt)).digest())


def signer_address(private_key_hex: str) -> str:
    """RECEIPT_SIGNING_KEY trong .env: khóa secp256k1 32 byte dạng hex. Trả về địa chỉ công khai."""
    return Account.from_key(private_key_hex).address


def sign_receipt(private_key_hex: str, key_no: int, seq: int, receipt: dict) -> str:
    """Chữ ký hệ thống trên biên nhận tạm (PB-02), hex 0x... 65 byte."""
    signed = Account.sign_message(encode_defunct(primitive=signed_message(key_no, seq, receipt)),
                                  private_key=private_key_hex)
    return "0x" + signed.signature.hex().removeprefix("0x")


def sign_record(private_key_hex: str, key_id: int, seq: int, record_hash: bytes) -> str:
    """Chữ ký trên bản ghi 164 byte (đích của đặc tả): EIP-191 trên 58 byte với recordHash thật của bản ghi."""
    signed = Account.sign_message(encode_defunct(primitive=build_signed_message(key_id, seq, record_hash)),
                                  private_key=private_key_hex)
    return "0x" + signed.signature.hex().removeprefix("0x")


def verify_record_signature(expected_address: str, key_id: int, seq: int, record_hash: bytes,
                            signature_hex: str) -> bool:
    try:
        recovered = Account.recover_message(encode_defunct(primitive=build_signed_message(key_id, seq, record_hash)),
                                            signature=bytes.fromhex(signature_hex.removeprefix("0x")))
    except (ValueError, TypeError, AttributeError, OverflowError, IndexError, BadSignature):
        return False
    return recovered.lower() == expected_address.lower()


def verify_signature(expected_address: str, key_no: int, seq: int, receipt: dict, signature_hex: str) -> bool:
    """Địa chỉ khôi phục từ chữ ký phải đúng địa chỉ khóa ký đã công bố.

    Chữ ký hỏng (sai hex, sai độ dài) cũng trả False, không ném lỗi ra /verify.
    """
    try:
        recovered = Account.recover_message(encode_defunct(primitive=signed_message(key_no, seq, receipt)),
                                            signature=bytes.fromhex(signature_hex.removeprefix("0x")))
    except (ValueError, TypeError, AttributeError, OverflowError, IndexError, BadSignature):
        return False
    return recovered.lower() == expected_address.lower()
