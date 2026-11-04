"""Dựng biên nhận tạm (ký bằng core.signing) và biên nhận hoàn chỉnh (thêm anchor + merkleProof)."""
from functools import lru_cache

from app.config import settings
from app.core.signing import load_private_key, public_key_b64, sign_receipt

RECEIPT_VERSION = "evidencechain-receipt-v1"
SIGNATURE_ALGORITHM = "Ed25519"


@lru_cache
def signing_key():
    return load_private_key(settings.receipt_signing_key)


def signing_public_key() -> str:
    return public_key_b64(signing_key())


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
        "signer": {"algorithm": SIGNATURE_ALGORITHM, "publicKey": signing_public_key()},
    }


def sign(receipt: dict) -> str:
    return sign_receipt(signing_key(), receipt)
