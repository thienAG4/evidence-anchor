"""Dựng biên nhận và ký.

Hai lớp chữ ký EIP-191, cùng khóa ký biên nhận, cùng 58 byte "EVC-RECEIPT-v1" ‖ keyId ‖ seq ‖ recordHash:
- Từng file: ký bản ghi 164 byte của file đó (seq, recordHash thật). Đây là chữ ký theo đặc tả; bản ghi
  được neo lên chuỗi nên chữ ký này nối thẳng biên nhận với dữ liệu công khai.
- Cả biên nhận: recordHash thay bằng SHA256(JSON biên nhận), seq là số của mã biên nhận. Lớp này giữ bundle,
  tên file, giờ có phần trăm giây (những thứ không nằm trong bản ghi 164 byte) khỏi bị sửa.
"""
from functools import lru_cache

from app.config import settings
from app.core.signing import sign_receipt, sign_record, signer_address, verify_record_signature, verify_signature

RECEIPT_VERSION = "evidencechain-receipt-v1"
SIGNATURE_ALGORITHM = "EIP-191"
FILE_KEYS = ("position", "fileName", "fileCode", "fileHash", "hashedAt", "timeHash", "leafHash")
RECORD_KEYS = ("seq", "recordHash", "recordSignature")


@lru_cache
def signing_address() -> str:
    """Địa chỉ của khóa ký biên nhận đang dùng (công khai qua GET /signing-key)."""
    return signer_address(settings.receipt_signing_key)


def receipt_seq(receipt: dict) -> int:
    """seq trong chữ ký cả biên nhận: phần số của mã biên nhận (TX-0004 -> 4)."""
    return int(receipt["receiptCode"].rsplit("-", 1)[1])


def record_signature(seq: int, record_hash_hex: str) -> str:
    return sign_record(settings.receipt_signing_key, settings.receipt_key_no, seq, bytes.fromhex(record_hash_hex))


def build_receipt(*, receipt_code: str, submission_type: str, owner: dict, submitted_at: str,
                  scheme: str, files: list[dict], bundle: dict, extra: dict | None = None) -> dict:
    """Biên nhận tự chứa: đủ dữ liệu để tự tính lại Ha, Habc, Bundle và kiểm chữ ký từng bản ghi."""
    return {
        "version": RECEIPT_VERSION,
        "receiptCode": receipt_code,
        "type": submission_type,
        "owner": owner,
        "submittedAt": submitted_at,
        "bundleScheme": scheme,
        "algorithm": "SHA-256",
        **(extra or {}),
        "files": [
            {k: f[k] for k in FILE_KEYS}
            | ({"sleepAfterSeconds": f["sleepAfterSeconds"]} if "sleepAfterSeconds" in f else {})
            | {k: f[k] for k in RECORD_KEYS if k in f}
            for f in files
        ],
        "bundle": bundle,
        "signer": {"algorithm": SIGNATURE_ALGORITHM, "keyNo": settings.receipt_key_no, "address": signing_address()},
    }


def sign(receipt: dict) -> str:
    return sign_receipt(settings.receipt_signing_key, receipt["signer"]["keyNo"], receipt_seq(receipt), receipt)


def verify(receipt: dict, signature: str, expected_address: str) -> bool:
    """Kiểm chữ ký cả biên nhận với địa chỉ khóa ký đã công bố (không lấy địa chỉ ghi trong biên nhận)."""
    try:
        key_no, seq = receipt["signer"]["keyNo"], receipt_seq(receipt)
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    return verify_signature(expected_address, key_no, seq, receipt, signature)


def verify_file_record(file: dict, key_no: int, expected_address: str) -> bool:
    """Chữ ký trên bản ghi của một file trong biên nhận. Biên nhận cũ (chưa có seq, recordHash) -> False."""
    try:
        record_hash = bytes.fromhex(file["recordHash"])
        if len(record_hash) != 32 or not isinstance(file["seq"], int):
            return False
        return verify_record_signature(expected_address, key_no, file["seq"], record_hash, file["recordSignature"])
    except (KeyError, TypeError, ValueError):
        return False
