"""Dựng biên nhận tạm (ký bằng core.signing) và biên nhận hoàn chỉnh (thêm anchor + merkleProof)."""
from functools import lru_cache

from app.config import settings
from app.core.signing import sign_receipt, signer_address, verify_signature

RECEIPT_VERSION = "evidencechain-receipt-v1"
SIGNATURE_ALGORITHM = "EIP-191"


@lru_cache
def signing_address() -> str:
    """Địa chỉ của khóa ký biên nhận đang dùng (công khai qua GET /signing-key)."""
    return signer_address(settings.receipt_signing_key)


def receipt_seq(receipt: dict) -> int:
    """Số thứ tự trong nội dung ký: phần số của mã biên nhận (TX-0004 -> 4), lấy từ sequence trong DB.

    Khi có bản ghi nhật ký 164 byte, thay bằng số thứ tự của bản ghi.
    """
    return int(receipt["receiptCode"].rsplit("-", 1)[1])


def build_receipt(*, receipt_code: str, submission_type: str, owner: dict, submitted_at: str,
                  scheme: str, files: list[dict], bundle: dict, extra: dict | None = None) -> dict:
    """Biên nhận tạm, tự chứa: đủ dữ liệu để tự tính lại Ha, Habc, Bundle mà không cần hỏi hệ thống."""
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
            {k: f[k] for k in ("position", "fileName", "fileCode", "fileHash", "hashedAt", "timeHash", "leafHash")}
            | ({"sleepAfterSeconds": f["sleepAfterSeconds"]} if "sleepAfterSeconds" in f else {})
            for f in files
        ],
        "bundle": bundle,
        "signer": {"algorithm": SIGNATURE_ALGORITHM, "keyNo": settings.receipt_key_no, "address": signing_address()},
    }


def sign(receipt: dict) -> str:
    return sign_receipt(settings.receipt_signing_key, receipt["signer"]["keyNo"], receipt_seq(receipt), receipt)


def verify(receipt: dict, signature: str, expected_address: str) -> bool:
    """Kiểm chữ ký với địa chỉ khóa ký đã công bố (không lấy địa chỉ ghi trong biên nhận)."""
    try:
        key_no, seq = receipt["signer"]["keyNo"], receipt_seq(receipt)
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    return verify_signature(expected_address, key_no, seq, receipt, signature)
