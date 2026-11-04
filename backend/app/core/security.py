"""Băm mật khẩu, tạo/đọc JWT."""
import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

# scrypt (thư viện chuẩn): N=2^14, r=8 -> ~16MB RAM mỗi lần băm, đủ chậm để chống dò mật khẩu.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
JWT_ALGORITHM = "HS256"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_password(password: str) -> str:
    """'scrypt$N$r$p$salt$hash' — lưu đủ tham số để sau này đổi tham số vẫn kiểm được mật khẩu cũ."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, base64.b64decode(expected))


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now,
               "exp": now + timedelta(minutes=settings.jwt_expire_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Ném jwt.PyJWTError nếu token sai chữ ký, hết hạn hoặc hỏng."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]})
