import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


def canonical_json(data: dict) -> bytes:
    """JSON cố định thứ tự khóa, không khoảng trắng — để ký và kiểm chữ ký cho cùng một chuỗi byte."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_private_key(seed_hex: str) -> Ed25519PrivateKey:
    """RECEIPT_SIGNING_KEY trong .env: 32 byte seed dạng hex."""
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex.removeprefix("0x")))


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def sign_receipt(private_key: Ed25519PrivateKey, receipt: dict) -> str:
    """Chữ ký hệ thống trên biên nhận tạm (PB-02), base64."""
    return base64.b64encode(private_key.sign(canonical_json(receipt))).decode("ascii")


def verify_signature(public_key_b64_value: str, receipt: dict, signature_b64: str) -> bool:
    """Chữ ký hoặc khóa hỏng (sai base64, sai độ dài) cũng trả False, không ném lỗi ra /verify."""
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64_value, validate=True))
        public_key.verify(base64.b64decode(signature_b64, validate=True), canonical_json(receipt))
        return True
    except (InvalidSignature, ValueError, TypeError):  # binascii.Error là con của ValueError
        return False
