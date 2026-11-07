"""Đăng nhập bằng tài khoản có sẵn (tên đăng nhập + mật khẩu), cấp JWT."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.enums import UserStatus
from app.db.models import User
from app.errors.codes import ErrorCode
from app.errors.handlers import AppError


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == normalize_username(username)))


def login(db: Session, username: str, password: str) -> User:
    """Mọi vai trò. Sai tên đăng nhập hay sai mật khẩu đều cùng một lỗi (không lộ tài khoản nào tồn tại)."""
    user = get_user_by_username(db, username)
    if user is None or user.status != UserStatus.ACTIVE or not verify_password(password, user.password_hash):
        raise AppError(401, ErrorCode.INVALID_CREDENTIALS, "Tên đăng nhập hoặc mật khẩu không đúng.")
    return user
